import threading
from RPLCD.i2c import CharLCD
import time
import random
import cv2
import numpy as np
import requests
import base64
from apikey import API_KEY
from gpiozero import Button, LED, Servo, Device
from gpiozero.pins.pigpio import PiGPIOFactory

Device.pin_factory = PiGPIOFactory()

upload_url = "".join([
    "https://detect.roboflow.com/",
    "green_belt/6",
    "?api_key=",
    API_KEY,
    "&format=json",
    "&stroke=5",
    "&confidence=30"
])

video = cv2.VideoCapture("/dev/video0")

no_water_btn = Button(5)
use_water_btn = Button(6)
water_pump = LED(13)

no_water_btn_status = 0
use_water_btn_status = 0

def press_5():
    global no_water_btn_status
    no_water_btn_status = 1

def release_5():
    global no_water_btn_status
    no_water_btn_status = 0

def press_6():
    global use_water_btn_status
    use_water_btn_status = 1

def release_6():
    global use_water_btn_status
    use_water_btn_status = 0

use_water_btn.when_pressed = press_6
use_water_btn.when_released = release_6
no_water_btn.when_pressed = press_5
no_water_btn.when_released = release_5

door_servo = Servo(19, min_pulse_width=0.55/1000, max_pulse_width=2.45/1000)
rotate_servo = Servo(26, min_pulse_width=0.55/1000, max_pulse_width=2.45/1000)

I2C_CHIP = "PCF8574"
I2C_ADDR = 0x27
LCD_COLS = 16
LCD_ROWS = 2

MAX_CCW = 700
MAX_CW = 2300

PLASTIC_BOTTLE = 5
TIN_CAN = 2
PAPER = 4

ACCEPTED = {PLASTIC_BOTTLE, TIN_CAN, PAPER}

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
    while not video.isOpened():
        pass

    door_servo.min()

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
        n = wait_for_trash()

        scroll1_event.clear()

        if n == PLASTIC_BOTTLE:
            lcd1.print("Detected:\r\nPlastic bottle")
            points += 70 
            rotate_servo.min()
        elif n == TIN_CAN:
            lcd1.print("Detected:\r\nAluminum can")
            points += 135
            rotate_servo.mid()
        elif n == PAPER:
            lcd1.print("Detected:\r\nPaper")
            points += 10
            rotate_servo.max()

        lcd2.print(f"Points: {points} mL")
        time.sleep(5)

        door_servo.mid()
        time.sleep(1.5)

        door_servo.min()
        time.sleep(0.5)

        rotate_servo.mid()

        time.sleep(3)

        scroll2_event.set()
        water = wait_for_button_press()
        
        scroll2_event.clear()

        if water:
            points = run_motor(points)
        

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


def wait_for_trash():
    data = infer()
    pred = data['predictions']
    print(pred)
    if len(pred) > 0:
        first = pred[0]['class_id']
        if first in ACCEPTED:
            return first

    return wait_for_trash()


def wait_for_button_press():
    while True:
        if use_water_btn_status == 1: 
            while not use_water_btn_status == 0:
                pass
            print("Use water")
            return True
        elif no_water_btn_status == 1:
            while not no_water_btn_status == 0:
                pass
            print("DO NOT use water")
            return False
        

def infer():
    # Get the current image from the webcam
    ret, img = video.read()

    # Resize (while maintaining the aspect ratio) to improve speed and save bandwidth
    height, width, channels = img.shape
    scale = 640 / max(height, width)
    img = cv2.resize(img, (round(scale * width), round(scale * height)))

    # Encode image to base64 string
    retval, buffer = cv2.imencode('.jpg', img)
    img_str = base64.b64encode(buffer)

    # Get prediction from Roboflow Infer API
    resp = requests.post(upload_url, data=img_str, headers={
        "Content-Type": "application/x-www-form-urlencoded"
    }, stream=True).json()

    # Parse result image
    return resp


def run_motor(points):
    water_pump.on()
    for i in range(points):
        if use_water_btn_status == 1: 
            while not use_water_btn_status == 0:
                pass
            break
        points -= 1        
        lcd2.print(f"Points: {points} mL")
        time.sleep(0.02)
    water_pump.off()
    return points


if __name__ == "__main__":
    try:
        main()
    finally:
        print("Stopping")

        video.release()
        cv2.destroyAllWindows()

        scroll1_event.set()
        kill1_event.set()

        scroll2_event.set()
        kill2_event.set()

        lcd1.close(clear=True)
        lcd2.close(clear=True)
