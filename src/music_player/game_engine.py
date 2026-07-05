import time
import random
from PIL import Image, ImageDraw

def run_snake_game(display, pn532, btn_left, btn_right, check_tag_removed_fn):
    """
    Runs a 1-bit Snake game on the Luma display.
    Controls:
      - btn_left (Vol Up): Turn Left relative to current direction
      - btn_right (Vol Down): Turn Right relative to current direction
    Exits if check_tag_removed_fn() returns True.
    """

    # Game dimensions
    GRID_WIDTH = 32
    GRID_HEIGHT = 16
    BLOCK_SIZE = 4  # 32 * 4 = 128, 16 * 4 = 64

    # Directions: 0=UP, 1=RIGHT, 2=DOWN, 3=LEFT
    DIR_UP = 0
    DIR_RIGHT = 1
    DIR_DOWN = 2
    DIR_LEFT = 3

    # State variables
    snake = []
    direction = DIR_RIGHT
    food = (0, 0)
    score = 0
    game_over = False
    
    # High score tracker (persists during the run session)
    if not hasattr(run_snake_game, "high_score"):
        run_snake_game.high_score = 0

    def reset_game():
        nonlocal snake, direction, food, score, game_over
        snake = [(16, 8), (15, 8), (14, 8)]
        direction = DIR_RIGHT
        score = 0
        game_over = False
        spawn_food()

    def spawn_food():
        nonlocal food
        while True:
            fx = random.randint(0, GRID_WIDTH - 1)
            fy = random.randint(0, GRID_HEIGHT - 1)
            if (fx, fy) not in snake:
                food = (fx, fy)
                break

    # Setup buttons
    turn_queue = []

    def handle_turn_left():
        if game_over:
            reset_game()
        else:
            turn_queue.append(-1)  # Turn left relative

    def handle_turn_right():
        if game_over:
            reset_game()
        else:
            turn_queue.append(1)  # Turn right relative

    # Backup existing button callbacks
    old_left_callback = btn_left.when_pressed
    old_right_callback = btn_right.when_pressed

    # Intercept button callbacks
    btn_left.when_pressed = handle_turn_left
    btn_right.when_pressed = handle_turn_right

    reset_game()
    last_update = time.time()
    # Speed of the snake (seconds per step)
    step_delay = 0.15

    print("[Game Engine] 1-Bit Snake Game Started.")

    try:
        while True:
            # Check if tag is removed
            if check_tag_removed_fn():
                print("[Game Engine] Tag removed. Exiting game loop...")
                break

            now = time.time()
            if not game_over:
                # Update every step_delay seconds
                if now - last_update >= step_delay:
                    last_update = now

                    # Process one turn from queue
                    if turn_queue:
                        turn = turn_queue.pop(0)
                        direction = (direction + turn) % 4

                    # Calculate new head position
                    head_x, head_y = snake[0]
                    if direction == DIR_UP:
                        head_y -= 1
                    elif direction == DIR_RIGHT:
                        head_x += 1
                    elif direction == DIR_DOWN:
                        head_y += 1
                    elif direction == DIR_LEFT:
                        head_x -= 1

                    # Collisions
                    if (head_x < 0 or head_x >= GRID_WIDTH or
                        head_y < 0 or head_y >= GRID_HEIGHT or
                        (head_x, head_y) in snake[:-1]):
                        game_over = True
                        if score > run_snake_game.high_score:
                            run_snake_game.high_score = score
                    else:
                        # Move snake
                        snake.insert(0, (head_x, head_y))
                        if (head_x, head_y) == food:
                            score += 10
                            spawn_food()
                            # Slightly speed up
                            step_delay = max(0.08, 0.15 - (score // 100) * 0.01)
                        else:
                            snake.pop()

            # Render frame
            with display.canvas() as draw:
                if game_over:
                    # Draw Game Over Screen
                    draw.rectangle((0, 0, 128, 64), fill="black")
                    draw.text((36, 6), "GAME OVER", fill="white")
                    draw.text((16, 22), f"Score: {score}  HI: {run_snake_game.high_score}", fill="white")
                    draw.text((6, 42), "Press Button to Restart", fill="white")
                else:
                    # Draw borders
                    draw.rectangle((0, 0, 128, 64), outline="white")
                    
                    # Draw food (draw as a small pixel cross or square)
                    fx, fy = food
                    px, py = fx * BLOCK_SIZE, fy * BLOCK_SIZE
                    draw.rectangle((px, py, px + BLOCK_SIZE - 1, py + BLOCK_SIZE - 1), fill="white")
                    
                    # Draw snake
                    for idx, (sx, sy) in enumerate(snake):
                        spx, spy = sx * BLOCK_SIZE, sy * BLOCK_SIZE
                        if idx == 0:
                            # Draw head with a tiny black dot in the center to distinguish it
                            draw.rectangle((spx, spy, spx + BLOCK_SIZE - 1, spy + BLOCK_SIZE - 1), fill="white")
                            draw.rectangle((spx + 1, spy + 1, spx + BLOCK_SIZE - 2, spy + BLOCK_SIZE - 2), fill="black")
                        else:
                            draw.rectangle((spx, spy, spx + BLOCK_SIZE - 1, spy + BLOCK_SIZE - 1), fill="white")
                            
                    # Draw micro HUD at top-right
                    draw.text((95, 2), f"S:{score}", fill="white")

            time.sleep(0.02)

    finally:
        # Restore old button callbacks
        btn_left.when_pressed = old_left_callback
        btn_right.when_pressed = old_right_callback
        print("[Game Engine] Snake game terminated and button callbacks restored.")
