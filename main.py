"""
Cheerlights Pico Bot
Find out more about Cheerlights at https://cheerlights.com/

* install "micropython-urequests"
* check for color updates every few minutes
* fast pulse the previous color before changing to the new one
* setup 8 LED buttons you can press to set the Cheerlights color using IFTTT + Twitter (optional)
* https://www.tomshardware.com/how-to/connect-raspberry-pi-pico-w-to-twitter-via-ifttt

Example:
// 20221114211907
// http://api.thingspeak.com/channels/1417/field/2/last.json
{
  "created_at": "2022-11-15T05:00:53Z",
  "entry_id": 881281,
  "field2": "#ffff00"
}
"""

import picokeypad as keypad
import WIFI_CONFIG
from network_manager import NetworkManager
import uasyncio
import urequests as requests
import ujson as json
import time
from pimoroni import RGBLED
from random import randint

##### Use your own key
IFTTT_KEY = "<your key here>"
#####

CHEERLIGHTS_URL = "http://api.thingspeak.com/channels/1417/field/2/last.json"
IFTTT_EVENT = "set_color"
WEBHOOK_URL = f"http://maker.ifttt.com/trigger/{IFTTT_EVENT}/with/key/{IFTTT_KEY}"
UPDATE_INTERVAL = 120  # refresh interval in secs. Be nice to free APIs!
NUM_PADS = keypad.get_num_pads()
SECONDS_PER_SLOW_PULSE = 4
CHOICES = { # https://www.colorhexa.com/
  "#0000ff": "blue",
  "#008000": "green",
  "#00ffff": "cyan",
  "#ff0000": "red",
  "#ff00ff": "magenta",
  "#895900": "orange",
  "#ff2349": "pink",
  "#ffff00": "yellow",
}
MAPPINGS = {
  "#ffa500": "#895900", # orange, highest tint
  "#ffc0cb": "#ff2349", # pink, second highest tint
}
END_TO_END_DELAY = 10 # from the time you press the button to when the API updates

def hex_to_rgb(hex):
  # converts a hex colour code into RGB
  h = hex.lstrip('#')
  r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
  return r, g, b

# set one side's LEDs to the same color
def illuminate_half(r, g, b):
  for i in range(8, NUM_PADS):
    keypad.illuminate(i, r, g, b)
  keypad.update()
  print(f"LEDs set to ({r}, {g}, {b})")

# fade in and out so it feels more alive
# this affects all LEDs on the board
def pulse(times=1, fast=False):
  delay = 0.0009 if fast else 0.001 # manually tested to get these values
  step = 0.0005
  min_b = 0.1
  max_b = 1.0

  for _ in range(times):
    brightness = max_b

    while brightness > min_b:
      brightness -= step
      if brightness < min_b:
        brightness = min_b
      keypad.set_brightness(brightness)
      keypad.update()
      time.sleep(delay)

    while brightness < max_b:
      brightness += step
      if brightness > max_b:
        brightness = max_b
      keypad.set_brightness(brightness)
      keypad.update()
      time.sleep(delay)

# only have room for 8 of the 11 possible choices
def setup_choices():
  index = 0
  choices = list(CHOICES.keys())
  for i in range(len(choices)):
    a, b, c = hex_to_rgb(choices[i])
    keypad.illuminate(i, a, b, c)
  keypad.update()

# check for a button press and hit the IFFF webhoook
def check(seconds):
  global last_button_states, lit
  start_time = time.ticks_ms()
  while True:
    button_states = keypad.get_button_states()
    if last_button_states != button_states:
        last_button_states = button_states
        if button_states > 0:
          button = 0
          for find in range(0, 8):
            # check if this button is pressed and no other buttons are pressed
            if button_states & 0x01 > 0:
                if not (button_states & (~0x01)) > 0:
                  url = f"{WEBHOOK_URL}?value1={list(CHOICES.values())[button]}"
                  print(f"pressed {button}") # button is 0-7 here
                  print(f"Requesting URL: {url} and waiting {END_TO_END_DELAY} seconds") # button is 0-7 here
                  requests.get(url)
                  time.sleep(END_TO_END_DELAY)
                  return
            button_states >>= 1
            button += 1
    current_time = time.ticks_ms()
    delta = current_time - start_time
    if delta > seconds * 1000:
      break

# set up wifi
network_manager = NetworkManager(WIFI_CONFIG.COUNTRY)

# set up the LEDs
keypad.init()
keypad.set_brightness(1.0)

previous = (255, 255, 255)
last_button_states = 0
lit = 0

setup_choices()

while True:
  try:
    # connect to wifi
    uasyncio.get_event_loop().run_until_complete(network_manager.client(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK))

    # open the json file
    print(f"Requesting URL: {CHEERLIGHTS_URL}")
    response = requests.get(CHEERLIGHTS_URL)
    data = json.loads(response.text)

    # extract hex colour from the data
    hex = data['field2']

    # map colors to optimize for the pico rgb keyboard
    if hex in MAPPINGS:
      hex = MAPPINGS[hex]

    # and convert it to RGB
    r, g, b = hex_to_rgb(hex)

    # pulse the previous color first
    print(f"Pulsing previous color ({previous[0]}, {previous[1]}, {previous[2]})")
    pulse(5, True)

    illuminate_half(r, g, b)

    # set it for the previous color
    previous = (r, g, b)

    check(UPDATE_INTERVAL)

  except Exception as err:
    # wait a bit and try again because network errors happen from time to time
    print(f"Unexpected {err=}, {type(err)=}. Trying again in 5 seconds ... ")
    time.sleep(5)
    pass
