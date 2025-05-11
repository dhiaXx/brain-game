import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext
import socket
import threading
import time


class TicTacToeEnhanced:
    """Enhanced Tic Tac Toe game with GUI, AI, and online multiplayer."""

    def __init__(self, master):
        """Initialize the Tic Tac Toe game with GUI and game logic."""
        print("Initializing Tic Tac Toe Enhanced...")
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
        self.is_host = False

    
        self.chat_box = None
        self.chat_entry = None

  
        self.setup_ui()
        if self.mode.get() == "Online":
            self.prompt_host_or_client()

    def setup_ui(self):
        """Set up the user interface for the game."""
        print("Setting up the UI...")
        mode_frame = tk.Frame(self.master, bg="#1e1e2f")
        mode_frame.pack(pady=10)
        for mode in ["PvP", "PvAI", "Online"]:
            tk.Radiobutton(
                mode_frame, text=mode, variable=self.mode, value=mode,
                command=self.reset_board, bg="#1e1e2f", fg="white", selectcolor="#2e2e4d"
            ).pack(side=tk.LEFT, padx=10)
        name_frame = tk.Frame(self.master, bg="#1e1e2f")
        name_frame.pack()
        self.name_vars = {'X': tk.StringVar(value="Player 1"), 'O': tk.StringVar(value="Player 2")}
        tk.Entry(name_frame, textvariable=self.name_vars['X'], width=15).pack(side=tk.LEFT, padx=10)
        tk.Entry(name_frame, textvariable=self.name_vars['O'], width=15).pack(side=tk.LEFT, padx=10)


        self.board_frame = tk.Frame(self.master, bg="#1e1e2f")
        self.board_frame.pack()
        for i in range(9):
            b = tk.Button(
                self.board_frame, text='', font=('Helvetica', 24, 'bold'), width=5, height=2,
                bg="#2e2e4d", fg="white", command=lambda i=i: self.make_move(i)
            )
            b.grid(row=i // 3, column=i % 3, padx=5, pady=5)
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
        """Update the score display."""
        print("Updating scores...")
        self.score_label.config(
            text=f"{self.name_vars['X'].get()} (X): {self.scores['X']} | "
                 f"{self.name_vars['O'].get()} (O): {self.scores['O']} | Ties: {self.scores['Tie']}"
        )


    def reset_board(self):
        """Reset the game board for a new game."""
        print("Resetting the board...")
        self.board = ['' for _ in range(9)]
        self.current_player = 'X'
        for btn in self.buttons:
            btn.config(text='', bg="#2e2e4d")
        if self.mode.get() == "Online":
            print("Setting up network for online mode...")
            self.prompt_host_or_client()
            threading.Thread(target=self.setup_network, daemon=True).start()

    def make_move(self, index):
        """Handle a player's move."""
        print(f"Player {self.current_player} attempting to make a move at index {index}...")
        if self.board[index] == '' and (self.mode.get() != "Online" or self.current_player == 'X'):
            self.board[index] = self.current_player
            self.update_buttons()
            if self.check_winner():
                winner = self.current_player
                self.scores[winner] += 1
                print(f"Player {winner} wins!")
                messagebox.showinfo("Game Over", f"{self.name_vars[winner].get()} wins!")
                self.update_score()
                self.reset_board()
                return
            elif '' not in self.board:
                self.scores['Tie'] += 1
                print("It's a tie!")
                messagebox.showinfo("Game Over", "It's a tie!")
                self.update_score()
                self.reset_board()
                return
            self.current_player = 'O' if self.current_player == 'X' else 'X'
            if self.mode.get() == "PvAI" and self.current_player == 'O':
                print("AI is making a move...")
                self.master.after(500, self.ai_move)
            elif self.mode.get() == "Online" and self.connection:
                print("Sending move to opponent...")
                self.send_move(index)

    def update_buttons(self):
        """Update the button texts to reflect the current board state."""
        print("Updating board buttons...")
        for i, val in enumerate(self.board):
            color = "#ff4d4d" if val == 'X' else "#4dff4d"
            self.buttons[i].config(text=val, fg=color if val else "white")

    def check_winner(self):
        """Check if there is a winner."""
        print("Checking for a winner...")
        wins = [(0, 1, 2), (3, 4, 5), (6, 7, 8),
                (0, 3, 6), (1, 4, 7), (2, 5, 8),
                (0, 4, 8), (2, 4, 6)]
        for a, b, c in wins:
            if self.board[a] == self.board[b] == self.board[c] and self.board[a] != '':
                for i in [a, b, c]:
                    self.buttons[i].config(bg="#ffcc00")
                return True
        return False

    def ai_move(self):
        """Simulate an AI move."""
        print("AI is making a move...")
        for i in range(9):
            if self.board[i] == '':
                self.make_move(i)
                break

    def setup_network(self):
        """Set up the network connection for online mode."""
        print("Setting up network...")
        if self.is_host:
            host_ip = socket.gethostbyname(socket.gethostname())
            print(f"Host IP: {host_ip}")
            messagebox.showinfo("Host Information", f"Your IP address is: {host_ip}\nShare this with your opponent.")
            threading.Thread(target=self.start_server, daemon=True).start()
        else:
            self.master.after(0, self.ask_for_ip)

    def start_server(self):
        """Start the server to listen for incoming connections."""
        try:
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            host_ip = socket.gethostbyname(socket.gethostname())
            self.connection.bind((host_ip, 12345))
            self.connection.listen(1)
            print(f"Server started on {host_ip}:12345. Waiting for opponent to connect...")
            self.log_chat(f"Server started on {host_ip}:12345. Waiting for opponent to connect...")
            conn, addr = self.connection.accept()
            print(f"Opponent connected from {addr}")
            self.connection = conn
            self.log_chat(f"Opponent connected from {addr}")
            threading.Thread(target=self.receive_data, daemon=True).start()
        except Exception as e:
            print(f"Error starting server: {e}")
            self.log_chat("Failed to start server.")
            messagebox.showerror("Server Error", "Failed to start server.")

    def ask_for_ip(self):
        """Prompt the user to enter the host IP."""
        ip = simpledialog.askstring("Connect", "Enter host IP:")
        if ip:
            print(f"Host IP entered: {ip}")
            self.connect_to_host(ip)

    def connect_to_host(self, ip):
        """Connect to the host using the provided IP address."""
        try:
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection.connect((ip, 12345))
            print(f"Connected to host at {ip}:12345.")
            self.log_chat(f"Connected to host at {ip}:12345.")
            threading.Thread(target=self.receive_data, daemon=True).start()
        except Exception as e:
            print(f"Error connecting to host: {e}")
            self.log_chat("Failed to connect to host.")
            messagebox.showerror("Connection Error", "Failed to connect to host.")

    def send_move(self, index):
        """Send the player's move to the opponent."""
        print(f"Sending move {index} to opponent...")
        try:
            self.connection.send(f"MOVE:{index}".encode())
        except:
            print("Failed to send move. Connection lost.")
            self.log_chat("Connection lost.")

    def receive_data(self):
        """Receive data from the opponent."""
        print("Receiving data from opponent...")
        while True:
            try:
                data = self.connection.recv(1024).decode()
                if data.startswith("MOVE:"):
                    index = int(data.split(":")[1])
                    print(f"Received move {index} from opponent.")
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
                    chat_message = data[5:]
                    print(f"Received chat message: {chat_message}")
                    self.log_chat("Opponent: " + chat_message)
            except:
                print("Disconnected from opponent.")
                self.log_chat("Disconnected from opponent.")
                break
                
    def send_chat(self, event):
        """Send a chat message to the opponent."""
        msg = self.chat_entry.get()
        if msg and self.connection:
            try:
                print(f"Sending chat message: {msg}")
                self.connection.send(f"CHAT:{msg}".encode())
                self.log_chat(f"You: {msg}")
                self.chat_entry.delete(0, tk.END)
            except Exception as e:
                print(f"Failed to send chat message: {e}")
                self.log_chat("Failed to send message.")

    def log_chat(self, message):
        """Log a chat message in the chat box."""
        print(f"Chat log: {message}")
        self.chat_box['state'] = 'normal'
        self.chat_box.insert(tk.END, message + "\n")
        self.chat_box['state'] = 'disabled'
        self.chat_box.see(tk.END)

   
    def prompt_host_or_client(self):
        """Prompt the user to choose if they are the host or client."""
        is_host = messagebox.askyesno("Host or Client", "Are you the host?")
        if is_host:
            self.is_host = True
            host_ip = socket.gethostbyname(socket.gethostname())
            print(f"Host IP: {host_ip}")
            self.log_chat(f"Your IP address is: {host_ip}. Share this with your opponent.")
            messagebox.showinfo("Host Information", f"Your IP address is: {host_ip}\nShare this with your opponent.")
        else:
            self.is_host = False
            self.master.after(0, self.ask_for_ip)


def show_splash_screen():
    """Display a splash screen before launching the main game."""
    splash = tk.Tk()
    splash.title("Welcome")
    splash.configure(bg="#1e1e2f")
    splash.geometry("400x300")
    splash.overrideredirect(True)


    tk.Label(splash, text="Tic Tac Toe", font=("Helvetica", 32, "bold"), fg="white", bg="#1e1e2f").pack(pady=50)
    tk.Label(splash, text="Enhanced Edition", font=("Helvetica", 16), fg="#ffcc00", bg="#1e1e2f").pack()

    tk.Label(splash, text="Loading...", font=("Helvetica", 12), fg="white", bg="#1e1e2f").pack(pady=20)

    
    splash.after(3000, splash.destroy)
    splash.mainloop()


if __name__ == "__main__":
    print("Starting the application...")
    show_splash_screen()
    root = tk.Tk()
    game = TicTacToeEnhanced(root)
    root.mainloop()
