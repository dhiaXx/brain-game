# brain-game
import tkinter as tk
from tkinter import messagebox

def display_board():
    for i in range(9):
        buttons[i].config(text=board[i], bg="white", fg="black")
        if board[i] == "X":
            buttons[i].config(fg="black")
        elif board[i] == "O":
            buttons[i].config(fg="green")

def check_winner(player):
    winning_combinations = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  
        [0, 4, 8], [2, 4, 6]              
    ]
    for combo in winning_combinations:
        if board[combo[0]] == board[combo[1]] == board[combo[2]] == player:
            return True
    return False

def check_tie():
    return all(cell != " " for cell in board)

def on_button_click(index):
    global current_player, x_score, o_score
    if board[index] == " ":
        board[index] = current_player
        display_board()
        if check_winner(current_player):
            messagebox.showinfo("Tic-Tac-Toe", f"Player {current_player} wins! 🎉")
            if current_player == "X":
                x_score += 1
            else:
                o_score += 1
            show_scoreboard()
        elif check_tie():
            messagebox.showinfo("Tic-Tac-Toe", "It's a tie! 😐")
            show_scoreboard()
        else:
            current_player = "O" if current_player == "X" else "X"
    else:
        messagebox.showwarning("Tic-Tac-Toe", "That cell is already taken! Try again.")
def show_scoreboard():
    scoreboard_window = tk.Toplevel(window)
    scoreboard_window.title("Scoreboard")
    scoreboard_window.configure(bg="black")

    tk.Label(scoreboard_window, text="Scoreboard", font=("Arial", 20), bg="black", fg="white").grid(row=0, column=0, columnspan=2, pady=10)
    tk.Label(scoreboard_window, text=f"Player X: {x_score}", font=("Arial", 16), bg="black", fg="white").grid(row=1, column=0, padx=10, pady=5)
    tk.Label(scoreboard_window, text=f"Player O: {o_score}", font=("Arial", 16), bg="black", fg="white").grid(row=1, column=1, padx=10, pady=5)

    tk.Button(scoreboard_window, text="Play Again", font=("Arial", 14), command=reset_game).grid(row=2, column=0, padx=10, pady=10)
    tk.Button(scoreboard_window, text="Quit", font=("Arial", 14), command=window.quit).grid(row=2, column=1, padx=10, pady=10)

def reset_game():
    global board, current_player
    board = [" " for _ in range(9)]
    current_player = "X"
    display_board()

board = [" " for _ in range(9)]
current_player = "X"  
x_score = 0
o_score = 0

window = tk.Tk()
window.title("Tic-Tac-Toe")
window.configure(bg="blue")
buttons = []
for i in range(9):
    button = tk.Button(window, text=" ", font=("Arial", 24), width=5, height=2, bg="white", command=lambda i=i: on_button_click(i))
    button.grid(row=i//3, column=i%3, padx=5, pady=5)
    buttons.append(button)
display_board()
window.mainloop()
