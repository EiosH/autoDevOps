# game_logic.py
def handle_player_inputs(input_commands, game_state):
    for command in input_commands:
        if command.lower() == 'restart':
            return {'command': 'restart'}, {'score': 0, 'lives': 3}  
        # Add more commands handling here
        elif command.lower() == 'exit':
            return {'command': 'exit'}, None  # End the game loop
    return None, game_state  # Return current game state without changes