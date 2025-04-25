# Enhanced Tic Tac Toe with local, AI, and online multiplayer modes
# Features: player names, scores, chat, and a vibrant GUI using tkinter

import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext
import socket
import threading

class TicTacToeEnhanced:
    def __init__(self, master):
        self.master = master
        self.master.title("Tic Tac Toe - Enhanced Edition")
        self.master.configure(bg="#1e1e2f")
        self.board = ['' for _ in range(9)]
        self.buttons = []
        self.current_player = "X"
        self.player_names = {'X': "Player 1", 'O': "Player 2"}
        self.scores = {'X': 0, 'O': 0, 'Tie': 0}
        self.mode = tk.StringVar(value="PvP")
        self.connection = None
        self.chat_box = None
        self.chat_entry = None
        self.is_host = False
        self.setup_ui()

    def setup_ui(self):
        mode_frame = tk.Frame(self.master, bg="#1e1e2f")
        mode_frame.pack(pady=10)
        for mode in ["PvP", "PvAI", "Online"]:
            tk.Radiobutton(mode_frame, text=mode, variable=self.mode, value=mode, command=self.reset_board,
                           bg="#1e1e2f", fg="white", selectcolor="#2e2e4d").pack(side=tk.LEFT, padx=10)

        name_frame = tk.Frame(self.master, bg="#1e1e2f")
        name_frame.pack()
        self.name_vars = {'X': tk.StringVar(value="Player 1"), 'O': tk.StringVar(value="Player 2")}
        tk.Entry(name_frame, textvariable=self.name_vars['X'], width=15).pack(side=tk.LEFT, padx=10)
        tk.Entry(name_frame, textvariable=self.name_vars['O'], width=15).pack(side=tk.LEFT, padx=10)

        self.board_frame = tk.Frame(self.master, bg="#1e1e2f")
        self.board_frame.pack()
        for i in range(9):
            b = tk.Button(self.board_frame, text='', font=('Helvetica', 24, 'bold'), width=5, height=2,
                          bg="#2e2e4d", fg="white", command=lambda i=i: self.make_move(i))
            b.grid(row=i//3, column=i%3, padx=5, pady=5)
            self.buttons.append(b)

        self.score_label = tk.Label(self.master, text="", font=("Arial", 14), fg="white", bg="#1e1e2f")
        self.score_label.pack(pady=5)

        control_frame = tk.Frame(self.master, bg="#1e1e2f")
        control_frame.pack()
        tk.Button(control_frame, text="Reset", command=self.reset_board, bg="#444", fg="white").pack(side=tk.LEFT, padx=10)

        self.chat_box = scrolledtext.ScrolledText(self.master, height=6, state='disabled', bg="#111", fg="lime", font=("Courier", 10))
        self.chat_entry = tk.Entry(self.master, bg="black", fg="lime")
        self.chat_entry.bind("<Return>", self.send_chat)
        self.chat_box.pack(fill=tk.X, padx=10, pady=(10, 0))
        self.chat_entry.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.update_score()

    def update_score(self):
        self.score_label.config(text=f"{self.name_vars['X'].get()} (X): {self.scores['X']} | "
                                     f"{self.name_vars['O'].get()} (O): {self.scores['O']} | Ties: {self.scores['Tie']}")

    def reset_board(self):
        self.board = ['' for _ in range(9)]
        self.current_player = 'X'
        for btn in self.buttons:
            btn.config(text='', bg="#2e2e4d")
        if self.mode.get() == "Online":
            threading.Thread(target=self.setup_network, daemon=True).start()

    def make_move(self, index):
        if self.board[index] == '' and (self.mode.get() != "Online" or self.current_player == 'X'):
            self.board[index] = self.current_player
            self.update_buttons()
            if self.check_winner():
                winner = self.current_player
                self.scores[winner] += 1
                messagebox.showinfo("Game Over", f"{self.name_vars[winner].get()} wins!")
                self.update_score()
                self.reset_board()
                return
            elif '' not in self.board:
                self.scores['Tie'] += 1
                messagebox.showinfo("Game Over", "It's a tie!")
                self.update_score()
                self.reset_board()
                return
            self.current_player = 'O' if self.current_player == 'X' else 'X'
            if self.mode.get() == "PvAI" and self.current_player == 'O':
                self.master.after(500, self.ai_move)
            elif self.mode.get() == "Online" and self.connection:
                self.send_move(index)

    def update_buttons(self):
        for i, val in enumerate(self.board):
            color = "#ff4d4d" if val == 'X' else "#4dff4d"
            self.buttons[i].config(text=val, fg=color if val else "white")

    def check_winner(self):
        wins = [(0,1,2), (3,4,5), (6,7,8),
                (0,3,6), (1,4,7), (2,5,8),
                (0,4,8), (2,4,6)]
        for a,b,c in wins:
            if self.board[a] == self.board[b] == self.board[c] and self.board[a] != '':
                for i in [a,b,c]:
                    self.buttons[i].config(bg="#ffcc00")
                return True
        return False

    def ai_move(self):
        for i in range(9):
            if self.board[i] == '':
                self.make_move(i)
                break

    def setup_network(self):
        if self.connection:
            self.connection.close()
        self.is_host = messagebox.askyesno("Online Mode", "Are you the host?")
        if self.is_host:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(("", 12345))
            server.listen(1)
            self.log_chat("Waiting for connection...")
            self.connection, _ = server.accept()
            self.log_chat("Player connected.")
            threading.Thread(target=self.receive_data, daemon=True).start()
        else:
            ip = simpledialog.askstring("Connect", "Enter host IP:")
            try:
                self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.connection.connect((ip, 12345))
                threading.Thread(target=self.receive_data, daemon=True).start()
                self.log_chat("Connected to server.")
            except:
                messagebox.showerror("Connection Failed", "Unable to connect.")

    def send_move(self, index):
        try:
            self.connection.send(f"MOVE:{index}".encode())
        except:
            self.log_chat("Connection lost.")

    def send_chat(self, event):
        msg = self.chat_entry.get()
        if msg and self.connection:
            try:
                self.connection.send(f"CHAT:{msg}".encode())
                self.log_chat(f"You: {msg}")
                self.chat_entry.delete(0, tk.END)
            except:
                self.log_chat("Failed to send message.")

    def log_chat(self, message):
        self.chat_box['state'] = 'normal'
        self.chat_box.insert(tk.END, message + "\n")
        self.chat_box['state'] = 'disabled'
        self.chat_box.see(tk.END)

    def receive_data(self):
        while True:
            try:
                data = self.connection.recv(1024).decode()
                if data.startswith("MOVE:"):
                    index = int(data.split(":")[1])
                    self.board[index] = self.current_player
                    self.update_buttons()
                    if self.check_winner():
                        self.scores[self.current_player] += 1
                        self.update_score()
                        messagebox.showinfo("Game Over", f"{self.name_vars[self.current_player].get()} wins!")
                        self.reset_board()
                        continue
                    elif '' not in self.board:
                        self.scores['Tie'] += 1
                        self.update_score()
                        messagebox.showinfo("Game Over", "It's a tie!")
                        self.reset_board()
                        continue
                    self.current_player = 'O' if self.current_player == 'X' else 'X'
                elif data.startswith("CHAT:"):
                    self.log_chat("Opponent: " + data[5:])
            except:
                self.log_chat("Disconnected from opponent.")
                break

if __name__ == "__main__":
    root = tk.Tk()
    game = TicTacToeEnhanced(root)
    root.mainloop()

