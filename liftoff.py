from time import sleep
from RPLCD import CharLCD
import RPi.GPIO as GPIO

lcd = CharLCD(cols=16, rows=2, pin_rs=4, pin_e=17, pins_data=[18, 22, 23, 24], numbering_mode=GPIO.BCM)
t = True

rocket11 = (
	0b00100,
	0b01010,
	0b10001,
	0b10001,
	0b10001,
	0b01010,
	0b01010,
	0b01010,)

lcd.create_char(0,rocket11)

rocket12 = (
	0b01010,
	0b01010,
	0b01010,
	0b01010,
	0b11011,
	0b11011,
	0b11111,
	0b10101,)

lcd.create_char(1,rocket12)

rocket21 = (
	0b10001,
	0b01010,
	0b01010,
	0b01010,
	0b01010,
	0b01010,
	0b01010,
	0b01010,)

lcd.create_char(2,rocket21)

rocket22 = (
	0b11011,
	0b11011,
	0b11111,
	0b10101,
	0b00100,
	0b01110,
	0b01110,
	0b11111,)

lcd.create_char(3,rocket22)

rocket32 = (
	0b00100,
	0b01110,
	0b01110,
	0b11111,
	0b11111,
	0b11111,
	0b01110,
	0b01010,)

lcd.create_char(5,rocket32)

rocket42 = (
	0b11111,
	0b11111,
	0b01110,
	0b01010,
	0b00000,
	0b00000,
	0b00000,
	0b00000,)

lcd.create_char(7,rocket42)

def display(l1, l2):
	global t
	lcd.clear()
	lcd.cursor_pos = (0,0)
	lcd.write_string(l1)
	lcd.cursor_pos = (1,0)
	lcd.write_string(l2)
	lcd.cursor_pos = (0,15)
	lcd.write_string(l1)
	lcd.cursor_pos = (1,15)
	lcd.write_string(l2)
	lcd.cursor_pos = (1,4)
	if t == True:
		lcd.write_string('LIFTOFF!')
		t = False
	else:
		t = True

while True:
	display('\x00','\x01')
	sleep(1)
	display('\x02','\x03')
	sleep(1)
	display('\x01','\x05')
	sleep(1)
	display('\x03','\x07')
	sleep(1)
	display('\x05',' ')
	sleep(1)
	display('\x07',' ')
	sleep(1)
	display(' ',' ')
	sleep(1)
