import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext

class TicTacToeEnhanced:
    def __init__(self, master):
        """Initialize the Tic Tac Toe game with GUI and game logic."""
        self.master = master
        self.master.title("Tic Tac Toe - Enhanced Edition")
        self.master.configure(bg="#2e3b4e")  # Dark Blue-Gray background
        self.board = ['' for _ in range(9)]
        self.buttons = []
        self.current_player = "X"
        self.player_names = {'X': "Player 1", 'O': "Player 2"}
        self.scores = {'X': 0, 'O': 0, 'Tie': 0}
        self.mode = tk.StringVar(value="PvP")
        self.get_player_names()

     
        self.setup_ui()

    def get_player_names(self):
        """Prompt players to enter their names."""
        player_x_name = simpledialog.askstring("Player X", "Enter name for Player X:")
        player_o_name = simpledialog.askstring("Player O", "Enter name for Player O:")

     
        self.player_names['X'] = player_x_name if player_x_name else "Player X"
        self.player_names['O'] = player_o_name if player_o_name else "Player O"

    def setup_ui(self):
        """Set up the user interface for the game."""
        # Mode selection
        mode_frame = tk.Frame(self.master, bg="#2e3b4e")
        mode_frame.pack(pady=10)
        for mode in ["PvP", "PvAI"]:
            tk.Radiobutton(mode_frame, text=mode, variable=self.mode, value=mode, command=self.reset_board,
                           bg="#2e3b4e", fg="white", selectcolor="#3c4f65").pack(side=tk.LEFT, padx=10)


        name_frame = tk.Frame(self.master, bg="#2e3b4e")
        name_frame.pack()
        self.name_vars = {'X': tk.StringVar(value=self.player_names['X']), 'O': tk.StringVar(value=self.player_names['O'])}
        tk.Entry(name_frame, textvariable=self.name_vars['X'], width=15, bg="#3c4f65", fg="white").pack(side=tk.LEFT, padx=10)
        tk.Entry(name_frame, textvariable=self.name_vars['O'], width=15, bg="#3c4f65", fg="white").pack(side=tk.LEFT, padx=10)

        self.board_frame = tk.Frame(self.master, bg="#2e3b4e")
        self.board_frame.pack()
        for i in range(9):
            b = tk.Button(self.board_frame, text='', font=('Helvetica', 24, 'bold'), width=5, height=2,
                          bg="#4a627a", fg="white", command=lambda i=i: self.make_move(i))
            b.grid(row=i//3, column=i%3, padx=5, pady=5)
            self.buttons.append(b)

        self.score_label = tk.Label(self.master, text="", font=("Arial", 14), fg="white", bg="#2e3b4e")
        self.score_label.pack(pady=5)

        control_frame = tk.Frame(self.master, bg="#2e3b4e")
        control_frame.pack()
        tk.Button(control_frame, text="Reset", command=self.reset_board, bg="#3c4f65", fg="white").pack(side=tk.LEFT, padx=10)

        self.update_score()

    def update_score(self):
        """Update the score display."""
        self.score_label.config(text=f"{self.name_vars['X'].get()} (X): {self.scores['X']} | "
                                     f"{self.name_vars['O'].get()} (O): {self.scores['O']} | Ties: {self.scores['Tie']}")

    def reset_board(self):
        """Reset the game board for a new game."""
        self.board = ['' for _ in range(9)]
        self.current_player = 'X'
        for btn in self.buttons:
            btn.config(text='', bg="#4a627a")

    def make_move(self, index):
        """Handle a player's move."""
        if self.board[index] == '':
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

    def update_buttons(self):
        """Update the button texts to reflect the current board state."""
        for i, val in enumerate(self.board):
            color = "#ff69b4" if val == 'X' else "#ffd700" if val == 'O' else "white"
            self.buttons[i].config(text=val, fg=color)

    def check_winner(self):
        """Check if there is a winner."""
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
        """Handle the AI's move."""
        for i in range(9):
            if self.board[i] == '':
                self.board[i] = self.current_player
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
                self.current_player = 'X'
                break

def show_splash_screen():
    """Display a splash screen before launching the main game."""
    splash = tk.Tk()
    splash.title("Welcome")
    splash.configure(bg="#2e3b4e")
    splash.geometry("400x300")
    splash.overrideredirect(True)

    title_label = tk.Label(splash, text="", font=("Helvetica", 32, "bold"), fg="sky blue", bg="#2e3b4e")
    title_label.pack(pady=50)

    subtitle_label = tk.Label(splash, text="Enhanced Edition", font=("Helvetica", 16), fg="#ffcc00", bg="#2e3b4e")
    subtitle_label.pack()

    loading_label = tk.Label(splash, text="Loading...", font=("Helvetica", 12), fg="white", bg="#2e3b4e")
    loading_label.pack(pady=20)

    game_title = "Tic Tac Toe"

    def animate_title(index=0):
        if index < len(game_title):
            title_label.config(text=game_title[:index + 1])
            splash.after(150, lambda: animate_title(index + 1))

    animate_title()
    splash.after(3000, splash.destroy)
    splash.mainloop()

if __name__ == "__main__":
    show_splash_screen()
    root = tk.Tk()
    game = TicTacToeEnhanced(root)
    root.mainloop()
