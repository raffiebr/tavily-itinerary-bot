import event_bot
import food_bot
import time

print("=== Running Events Bot ===")
event_bot.main()

time.sleep(2)  # Small delay between messages

print("\n=== Running Food Bot ===")
food_bot.main()

print("\n🎉 All done!")
