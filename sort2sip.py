import threading
from RPLCD.i2c import CharLCD
import pigpio
import time
import random

pi = pigpio.pi()

I2C_CHIP = "PCF8574"
I2C_ADDR = 0x27
LCD_COLS = 16
LCD_ROWS = 2

SERVO_DOOR = 13
SERVO_ROTATE = 19

MAX_CCW = 700
MAX_CW = 2300

class LCD(CharLCD):
    _lock = threading.Lock()
    _scroll_event = threading.Event()
    _kill_event = threading.Event()

    def print(self, message, clear=True):
        self._lock.acquire()
        if clear:
            self.clear()
        self.write_string(message)
        self._lock.release()

    def safe_clear(self):
        self._lock.acquire()
        self.clear()
        self._lock.release()


lcd1 = LCD(I2C_CHIP, I2C_ADDR, None, 3, LCD_COLS, LCD_ROWS)
lcd2 = LCD(I2C_CHIP, I2C_ADDR, None, 1, LCD_COLS, LCD_ROWS)

scroll1_event = threading.Event()
kill1_event = threading.Event()

scroll2_event = threading.Event()
kill2_event = threading.Event()

def main():
    welcome_thread = threading.Thread(
        target=print_scroll,
        args=(
            lcd1,
            "Welcome to Sort2Sip! To start, throw your trash below. Points in the form of mineral water will be awarded for each type and quantity of trash.",
            scroll1_event,
            kill1_event
        ),
    )

    redeem_thread = threading.Thread(
        target=print_scroll,
        args=(
            lcd2,
            "You can choose to either redeem your points now, or leave it for the next user.",
            scroll2_event,
            kill2_event
        ),
    )

    welcome_thread.start()
    redeem_thread.start()
    points = 0

    while True:
        scroll1_event.set()
        scroll2_event.clear()

        lcd2.print(f"Points: {points} mL")
        input()

        scroll1_event.clear()

        lcd1.print("Detecting...")
        time.sleep(0.5)

        n = random.randint(0, 2)
        angle = 0
        if n == 0:
            lcd1.print("Detected:\r\nPlastic bottle")
            points += 96
        elif n == 1:
            lcd1.print("Detected:\r\nColored paper")
            points += 13
            angle = 90
        elif n == 2:
            lcd1.print("Detected:\r\nWhite paper")
            points += 8
            angle = 180

        pi.set_servo_pulsewidth(19, 700)
        time.sleep(0.5)

        pi.set_servo_pulsewidth(13, 1800)
    
        lcd2.print(f"Points: {points} mL")

        time.sleep(5)

        scroll2_event.set()
        input()


def print_scroll(lcd, message, scroll_event, kill_event):
    while True:
        for i in range(LCD_COLS, len(message) + 1):
            scroll_event.wait()
            if kill_event.is_set():
                return
            
            substr = message[i - LCD_COLS : i]
            if i == LCD_COLS or i == len(message):
                for j in range(3):
                    lcd.print(substr)
                    time.sleep(0.3)
                    lcd.safe_clear()
                    time.sleep(0.3)
            else:
                lcd.print(substr)
                time.sleep(0.3)


def map_degrees_to_servo(ccw, cw, deg):
    range = cw - ccw
    percent = deg / 180
    motion = round(range * percent)

    return ccw + motion


if __name__ == "__main__":
    try:
        main()
    except:
        print("Stopping")

        scroll1_event.set()
        kill1_event.set()

        scroll2_event.set()
        kill2_event.set()

        pi.set_servo_pulsewidth(SERVO_ROTATE, 0)
        pi.set_servo_pulsewidth(SERVO_DOOR, 0)

        lcd1.close(clear=True)
        lcd2.close(clear=True)
