######################################################################################################
#	Die Darstellung erfolgt auf einem 16x2 LCD character-Display für die Informationen
#	und einem 4-stelligen 7-Segment-Display mit zentralem Doppelpunkt und I2C Backpack für Zeiten
#	und den Countdown.
#
#	
#
#	Autor: Kai Arnetzl
######################################################################################################

#importiere alle benötigten Module
from decimal import *
import requests
import json
import threading
import time
import random
import pygame
import subprocess
import sys
import os
from datetime import datetime
import RPi.GPIO as GPIO
from RPLCD import CharLCD
from Adafruit_LED_Backpack import SevenSegment
#deklariere benötigte globale Variablen und Objekte
#TODO: weniger globale Variablen
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(14,GPIO.OUT)
GPIO.setup(17,GPIO.OUT)
segment = SevenSegment.SevenSegment() #initialisiert Siebensegmentdisplay mit Standardadresse
lcd = CharLCD(cols=16, rows=2, pin_rs=4, pin_e=17, pins_data=[18,22,23,24],numbering_mode = GPIO.BCM) #initialisiert LDC Display mit verwendeten Pins
launchtime = 0	#Unixtimestamp des nächsten Starts
launchid = 0	#ID des aktuellen Starts in der Launchlibrary-Datenbank
end = True #Wurde Start abgesagt/ ist Mission zuende? (egal ob erfolgreich oder nicht)
phase = 0 #aktuelle Phase des Starts
mode = True #True = clock, False = launch only
data = {}
colon = True #Zustand des Doppelpunktes auf dem 7 Segment Display
engineLED = GPIO.PWM(14, 100) #Pin der Triebwerk-Leds
spotLED = GPIO.PWM(18, 100) #Pin der Scheinwerfer-Leds
GPIO.setup(15, GPIO.OUT)
GPIO.output(15, GPIO.HIGH)
segment.begin()
pygame.init()
track = pygame.mixer.Sound('Rocket_Start_Track.wav')

# Benutzerdefinierte Zeichen für das LCD-Display, wenn in der richtigen Reihenfolge dargestellt ergeben diese eine Animation einer startenden Rakete
rocket_char_0 = (
	0b00100,
	0b01010,
	0b10001,
	0b10001,
	0b10001,
	0b01010,
	0b01010,
	0b01010,)
lcd.create_char(0,rocket_char_0)
rocket_char_1 = (
	0b01010,
	0b01010,
	0b01010,
	0b01010,
	0b11011,
	0b11011,
	0b11111,
	0b10101,)
lcd.create_char(1,rocket_char_1)
rocket_char_2 = (
	0b10001,
	0b01010,
	0b01010,
	0b01010,
	0b01010,
	0b01010,
	0b01010,
	0b01010,)
lcd.create_char(2,rocket_char_2)
rocket_char_3 = (
	0b11011,
	0b11011,
	0b11111,
	0b10101,
	0b00100,
	0b01110,
	0b01110,
	0b11111,)
lcd.create_char(3,rocket_char_3)
rocket_char_4 = (
	0b00100,
	0b01110,
	0b01110,
	0b11111,
	0b11111,
	0b11111,
	0b01110,
	0b01010,)
lcd.create_char(4,rocket_char_4)
rocket_char_5 = (
	0b11111,
	0b11111,
	0b01110,
	0b01010,
	0b00000,
	0b00000,
	0b00000,
	0b00000,)
lcd.create_char(5,rocket_char_5)

class button:	#Klasse für die Knöpfe im Gehäuse
	def __init__(self, pin, short_func = None, long_func = None, led_pin = 0, debounce = 0.05, long_press = 0.5):
		self.pin = pin
		self.led_pin = led_pin
		self.short_func = short_func
		self.long_func = long_func
		self.debounce = debounce
		self.long_press = long_press
		self.state = 0
		self.led_state = False
		self.blinking = False
		GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.add_event_detect(self.pin, GPIO.FALLING, callback=self.callbackEvent, bouncetime = self.debounce * 1000)
		if self.led_pin > 0:
			GPIO.setup(self.led_pin, GPIO.OUT)
			GPIO.output(self.led_pin, GPIO.LOW)

	def callbackEvent(self, channel):
		start_time = time.time()
		while GPIO.input(channel) == 0:
			time.sleep(0.01)
		buttonTime = time.time() - start_time
		if self.debounce <= buttonTime < self.long_press:
			self.state = 1
			if self.short_func is not None:
				self.short_func()
		elif self.long_press <= buttonTime:
			self.state = 2
			if self.long_func is not None:
				self.long_func()

	def readState(self):
		og_state = self.state
		self.state = 0
		return og_state

	def isPressed(self):
		if GPIO.input(self.pin) == False:
			return True
		else:
			return False

	def setLed(self, state):
		if state == True:
			GPIO.output(self.led_pin, GPIO.HIGH)
			self.led_state = True
		else:
			GPIO.output(self.led_pin, GPIO.LOW)
			self.led_state = False

	def blinkLed(self, frequency):
		if self.blinking == False:
			self.blinking = True
			blink = threading.Thread(target=self.blinkFunction, args=(frequency,), daemon = True)
			blink.start()

	def blinkFunction(self, frequency):
		og_state = self.led_state
		while og_state == self.led_state:
			GPIO.output(self.led_pin, GPIO.HIGH)
			time.sleep(frequency)
			GPIO.output(self.led_pin, GPIO.LOW)
			time.sleep(frequency)
		self.setLed(self.led_state)
		self.blinking = False

class settingMenu:
	def __init__(self, settings_dict = {}):
		self.setting = 0
		self.step = 0.5
		self.presses = 0
		self.last_press = 0
		self.audio_mute = False
		self.active = False
		self.settings_dict = settings_dict
	def open(self):
		self.active = True
		self.setting = 0
		lcd.clear()
		lcd.cursor_pos = (0,0)
		lcd.write_string(self.settings_dict[0]['name'])
		if self.settings_dict[0]['type'] == 'bar':
			lcd.write_string(self.bar(self.settings_dict[0]['value']))
		elif self.settings_dict[0]['type'] == 'bool':
			lcd.write_string(self.bool(self.settings_dict[0]['value']))
		else
			lcd.write_string(self.delay(self.settings[0]['value']))
	
	def showNew(self):
		lcd.clear
		lcd.cursor_pos = (0,0)
		lcd.write_string(self.settings_dict[self.setting]['name'])
		lcd.cursor_pos = (1,0)
		if self.settings_dict[self.setting]['type'] == 'bar':
			lcd.write_string(self.bar(self.settings_dict[self.setting]['value']))
		elif self.settings_dict[self.setting]['type'] == 'bool':
			lcd.write_string(self.bool(self.settings_dict[self.setting]['value']))
		else
			lcd.write_string(self.delay(self.settings_dict[self.setting]['value']))
	
	def next(self):
		if self.active:
			self.setting += 1
			if self.setting = 3:
				self.setting = 0
			self.showNew()
		else:
			self.open()
	
	def prev(self):
		if self.active:
			self.setting -= 1
			if self.setting = -1:
				self.setting = 2
			self.showNew()
		else:
			self.open()
			
	def bar(self, value):
		line_string = ''
		for i in range(0,value):
			line_string += char(255)
		line_string = line_string.ljust(16)
		return line_string
	
	def delay(self, value):
		minutes = int((self.settings_dict[self.setting]['value']/60)%60)
		seconds = int(self.settings_dict[self.setting]['value'] % 60)
		halves = '0'
		if self.settings_dict[self.setting]['value'].is_integrer:
			halves = '5'
		line_string = '    %02d:%02d.%s' % (minutes, seconds, halves)
		return line_string
		
	def bool(self, value):
		if value == True:
			state = 'On'
		else:
			state = 'Off'
		line_string = state.center(16)
		return line_string
	
	def left(self):
		if self.active:
			if self.settings_dict[self.setting]['type'] == 0:
				self.settings_dict[self.setting]['value'] -= 1
			elif self.settings_dict[self.setting]['type'] == 1:
				self.settings_dict[self.setting]['value'] != self.settings_dict[self.setting]['value']
			else:	#Verändern der Verzögerung, Änderung per Knopfdruck steigt wenn dieser schnell gedrückt wird
				if time.time() - self.last_press <= 0.75:
					self.presses += 1
					if self.presses == 5 and self.step < 32:
						self.step = self.step * 2
				else:
					self.presses = 0
					self.step = 0.5
				self.settings_dict[self.setting]['value'] += self.step
				self.settings_dict[self.setting]['value'] = min(self.settings_dict[self.setting]['value'], 1800])
				self.last_press = time.time()
			
	def right(self):
		if self.active:
			if self.settings_dict[self.setting]['type'] == 0:
				self.settings_dict[self.setting]['value'] += 1
			elif self.settings_dict[self.setting]['value'] == 1:
				self.settings_dict[self.setting]['value'] != self.settings_dict[self.setting]['value']
			else:
				if time.time() - self.last_press <= 0.75:
					self.presses += 1
					if self.presses == 5 and self.step < 32:
						self.step = self.step * 2
				else:
					self.presses = 0
					self.step = 0.5
				self.settings_dict[self.setting]['value'] -= self.step
				self.settings_dict[self.setting]['value'] = max(self.settings_dict[self.setting]['value'], 0])
				self.last_press = time.time()
				 
	def update(self):
		lcd.cursor_pos = (1,0)
		if self.settings_dict[self.setting]['type'] == 0:
			lcd.write_string(self.bar(self.settings_dict[self.setting]['value']))
		elif self.settings_dict[self.setting]['type'] == 1:
			lcd.write_string(self.bool(self.settings_dict[self.setting]['value']))
		else
			lcd.write_string(self.delay(self.settings_dict[self.setting]['value']))
	
	def shutdown(self):
		phase = 0
		end = True
		time.sleep(2)	#Damit alle Threads beendet sind
		segment.clear()
		lcd.clear()
		lcd.cursor_pos = (0,0)
		lcd.write_string("     Goodbye")
		time.sleep(2)
		subprocess.call(['shutdown', '-h', 'now'], shell=False)

	def mute(self):
		if self.audio_mute == False:
			track.set_volume(0)
			self.audio_mute = True
		else:
			track.set_volume(self.settings_dict[1]['value'])
			self.audio_mute  = False

class LCDwriter():
	def __init__(self, lcd_obj):
		self.lcd = lcd_obj
		self.power = True
		self.new = True
		self.running = False
		self.queue = {'line1':'', 'format_line1':0, 'line2':'', 'format_line2':0, 'priority':-1, 'duration':0}
		self.current_continous = {'line1':'', 'format_line1':0, 'line2':'', 'format_line2':0, 'priority':0, 'duration':0}
		self.showing = {'line1':'', 'format_line1':0, 'line2':'', 'format_line2':0, 'priority':0, 'duration':0}
		
	def startWriter(self):
		if self.running == False:
			self.running = True
			writer = threading.Thread(target=self.writerFunction, daemon = True)
			writer.start()
			
	def write(self, line1, format_line1 = 0, line2, format_line2 = 0, priority = 0, duration = 0):
		self.queue = [line1, format_line1, line2, format_line2, priority, duration]
		self.new = True
		self.startWriter()
		
	def setPower(self, state):
		self.power = state
		
	def setBrightness(self, brightness):
		#analogen Output auf Wert setzen (16 Stufen)
	
	def writerFunction(self):
		while self.power == True:
			if self.new == True and self.queue['priority'] >= self.showing['priority'] or self.queue['priority'] == -1:
				if self.showing['duration'] == 0:
					self.current_continous = self.showing.copy()
				if self.queue['line1'] != 3:
					self.showing['line1'] = self.queue['line1']
					self.showing['format_line1'] = self.queue['format_line1']
				if self.queue[3] != 3:
					self.showing[2] = self.queue[2]
					self.showing[3] = self.queue[3]
				self.showing[4] = self.queue[4]
				self.showing[5] = self.queue[5]
				if self.queue[4] == -1:
					self.showing = self.current_continous.copy()
				
				hold_time = time.time()
				max_length = len(line1)
				if len(line2) > max_length:	#Wie lang ist der längste String?
				max_length = len(line2)
				if len(line1) <= 16:	#Schreib Zeile 1 auf LCD falls diese komplett passt (maximale Länge ist 16 Zeichen)
					lcd.cursor_pos = (0,0)
					if self.showing[1] == 0:
						print_line = self.showing[0].ljust(16)
					elif self.showing[1] == 1:
						print_line = self.showing[0].center(16)
					else:
						print_line = self.showing[0].rjust(16)
					self.lcd.write_string(print_line)
				if len(line2) <= 16:	#Schreib Zeile 2 auf LCD falls diese komplett passt (maximale Länge ist 16 Zeichen)
					lcd.cursor_pos = (1,0)
					if self.showing[3] == 0:
						print_line = self.showing[2].ljust(16)
					elif self.showing[3] == 1:
						print_line = self.showing[2].center(16)
					else:
						print_line = self.showing[2].rjust(16)
					self.lcd.write_string(print_line)
				
				
				if if max_length > 16 and i < max_length - 15 and i > -1:
					if wait_until >= time.time():
						wait_until = time.time()
						if len(line1) > 16 and len(line1) >= i + 16:	#Falls Zeile 1 zu lang ist, scrolle diese
							self.lcd.cursor_pos = (0,0)
							self.lcd.write_string(line1[i:i+16])
						if len(line2) > 16 and len(line2) >= i + 16:	#Falls Zeile 2 zu lang ist, scrolle diese
							self.lcd.cursor_pos = (1,0)
							self.lcd.write_string(line2[i:i+16])
						if i == 0:	#Warte 1 Sekunde bevor gescrollt wird, scrolle anschließend mit 0,4 Sekunden/Zeichen
							wait_until += 1
						else:
							wait_until += 0.4
						i += 1
				else:
					i = -1
				
				if self.showing[6] > 0:
					while hold_time + self.showing[6] > time.time():
						
					if 

settingController = settingMenu({0: {'name':'brightness', 'type': 'bar',   'value': 8},
				 1: {'name':'volume', 	  'type': 'bar',   'value': 8},
				 2: {'name':'delay', 	  'type': 'timer', 'value': 0}})
LightB = button(20, led_pin = 21)
ModeB_left = button(26, settingController.left, settingController.next)
ModeB_right = button(19, settingController.right, settingController.prev)
PowerB = button(16, settingController.mute, settingController.shutdown)


def rocketengines():	#Flackern der Leds in den Triebwerken
	engineLED.start(0)
	for b in range(0,60):	#Für 3 Sekunden wird geflacker immer heller
		engineLED.ChangeDutyCycle(random.uniform(0,b))
		time.sleep(0.05)
	while phase == 5:
		engineLED.ChangeDutyCycle(random.uniform(30,100))
		time.sleep(0.05)

def engineFadeout():	#Leds in den Triebwerken glühen für ~10 Sekunden aus
	for b in range(0,61):
		engineLED.ChangeDutyCycle(60 - i)
		time.sleep(0.15)
	engineLED.off()

def spotlight():	#Anschalten der Scheinwerfer
	for b in range(0,100):	#Scheinwerfer werden für 50 Sekunden immer heller
		spotLED.ChangeDutyCycle(b)
		time.sleep(0.5)
	spotLED.on() 	#Scheinwerfer werden auf voller Helligkeit angelassen
	
def spotlightFadeout():	#Scheinwerfer werden langsam ausgeschaltet
	for b in range(0,100):
		spotLED.ChangeDutyCycle(100 - i)
		time.sleep(0.5)
	spotLED.off()

def updatethread():	#Startzeit der nächsten Rakete wird ständig aus dem Internet gelesen und aktualisiert
	global launchtime
	global launchid
	global end
	global data
	last_check = 0
	interval = 0
	while True:
		if time.time() >= last_check + interval:
			if launchtime - time.time() >= 0 or launchtime - time.time() < -3598:
				r = requests.get("https://launchlibrary.net/1.4.2/launch/next/1")	#Anfrage an Web-API, erhält JSON-Datei zurück
			else:
				r = requests.get("https://launchlibrary.net/1.4.2/launch/" + str(launchid)) #Die Start-Reihenfolge der API rückt schnell nach dem Start aus, durch das Verwenden der ID wird verhindert, dass der nächste Start abgefragt wird während der Alte noch läuft.
			data = r.json() #Wandel JSON in dictionary um
			launchid = (data["launches"][0]["id"])
			status = (data["launches"][0]["status"])	#Auslesen des Status des nächsten Starts
			if status == 1:		#Status 1 = Startzeit der Rakete steht fest und Rakete hat GO
				launchtime = (data["launches"][0]["netstamp"])	#Startzeit wird ausgelesen und aktualisiert
				end = False
			elif status == 2 or status == 5:	#Status 2 = Startzeit nicht festgelegt oder Rakete hat NO GO, Status 5 = Start pausiert
				end = True	#Abbruch Startsequenz
			if phase == 5:
				isPhase6(status)
			if phase > 1:
				interval = 20	#Ab Phase 2: Aktualisiere alle 20 Sekunden
			else:
				interval = 60	#Vor Phase 2: Warte 1 Minute bis zum erneuten Aktualisieren
			last_check = time.time()
			
			if launchtime - time.time() < 3:
				phase = 5
			elif launchtime - time.time() < 7:
				phase = 4
			elif launchtime - time.time() < 61:
				phase = 3
			elif launchtime - time.time() < 3600:
				phase = 2
			elif launchtime - time.time() < 18000:
				phase = 1
			else:
				phase = 0
			if end = True:
				phase = 0

def isPhase6(status):
	if status == 3 and phase > 0:		#Status 3 = Start erfolgreich
		display("    SUCCSESS!"," ")
		end = True
	elif status == 4 and phase > 0:		#Status 4 = Start fehlgeschlagen
		display("     FAILURE"," ")
		end = True
	elif status == 7 and phase > 0:		#Status 7 = Teilweiser Fehlschlag (z.B. nicht stabiler Orbit)
		display("     PARTIAL","     FAILURE")
		end = True
	elif (time.time() - launchtime) > 3598:	#Timeout; nach 60 Minuten wird Start als abgeschlossen angesehen
		display("     TIMEOUT", " ")
		end = True

def countdownthread():	#Countdown ab T-59:59
	global colon
	oldTime = time.time()
	while phase >= 2:	#Beenden, sollte Start abgebrochen oder abgeschlossen worden sein
		rtime = int(time.time())
		firstDigit = '0'
		if launchtime >= rtime:
			seconds = launchtime - rtime
			firstDigit = '-'
		else:
			seconds = rtime - launchtime	#nach T-0 (Start) wird Zeit seit Start angezeigt
		if rtime > oldTime:	#ist eine Sekunde vergangen?
			oldTime = rtime
			finalS = str(int(seconds % 60))
			finalM = str(int((seconds/60)%60))
			if len(finalS) == 1:
				finalS = '0' + finalS
			if len(finalM) == 1:
				finalM = firstDigit + finalM
			ftime = finalM + finalS
			segmentClock(ftime)	#Stelle Countdown auf 7 Segment Display dar
			colon = not colon	#Doppelpunkt auf Display blinkt mit 0,5 Hertz
		time.sleep(0.1)

def segmentClock(clock):	#Stelle eine Zeit(String) auf dem 7 Segment Display dar
	segment.set_colon(colon)
	for i in range(0,4):
		segment.set_digit(i, clock[i])
	segment.write_display()

def displayInfo():	#Stelle Informationen zu der Mission auf LCD dar
	oldTime = 0
	name, launchpad, mission, lsp = getInfo()
	while phase >= 1:
		while int(time.time()) < (oldTime+10):
			time.sleep(0.1)
			while settingMode.showing == True:
				time.sleep(0.1)
		oldTime = int(time.time())
		display(name, lsp)	#Zeige für 10 Sekunden Name der Rakete & Mission und Launch Service Provider
		while int(time.time()) < (oldTime+10):
			time.sleep(0.1)
			while settingMode.showing == True:
				time.sleep(0.1)
		oldTime = int(time.time())
		display(mission, launchpad)	#Zeige für 10 Sekunden Art der Mission und Start

def display(line1, line2, priority = 0, duration = 0):	#Stelle 2 Zeilen auf LCD Display dar. Scrolle falls nötig.
	
		
def clearLine(line):	#löscht nur den Inhalt einer Zeile, nicht gleich beide. "line" kann 0 oder 1 sein.
	lcd.cursor_pos = (line,0)
	lcd.write_string("                ")

def getInfo():	#erhalte Informationen zum Start von Web-API
	try:
		name = (data["launches"][0]["name"])	#lies Namen der Rakete & Mission ab
		launchpad = (data["launches"][0]["location"]["name"])	#lies Ort der Startrampe ab
		mission = (data["launches"][0]["missions"][0]["typeName"])	#lies Art der Mission (z.B. Kommunikation) ab
		lsp = (data["launches"][0]["lsp"]["name"])	#lies den Namen des Launch Service Providers (z.B. SpaceX) ab
		return (name, launchpad, mission, lsp)
	except:
		return (" "," "," "," ")

def displaytime():
	colon = True	#Doppelpunkt auf Display ist dauerhaft an
	segmentClock(datetime.fromtimestamp(launchtime).strftime('%H%M'))	#Stelle die Startzeit der Rakete in der eingestellten Zeitzone auf dem 7 Segment Display dar


updatelaunch = threading.Thread(target=updatethread)
info = threading.Thread(target=displayInfo)
countdown = threading.Thread(target=countdownthread)
updatelaunch.start()	#Fang an, Startzeit und Status regelmäßig zu aktualisieren
display("    Starting"," ")
while True:
	#Phase 0: Warte, bis der nächste Start einer Rakete 5 Stunden entfernt ist
	#Setze alle Anzeigen und LEDs zurück
	phase = 0
	spotLED.off()
	engineLED.off()
	lcd.clear()
	segment.clear()
	segment.set_brightness(7)
	segment.write_display()
	while launchtime - time.time() >= 21600 or end == True:
		time.sleep(10)
	#Phase 1: Start liegt weniger als 5 Stunden in der Zukunft, zeige Startzeit und Informationen an
	phase = 1
	displaytime()
	info.start()

	waitForT(3600, 1)	#Warte bis zur nächsten Phase
	if end == True:	#Kehre zu Phase 0 zurück falls Start abgebrochen wurde
		continue
	#Phase 2: Start in einer Stunde, zeige den Countdown an
	phase = 2
	segment.set_brightness(15)
	countdown.start()

	waitForT(61, 1)		#Warte bis zur nächsten Phase
	if end == True:	#Kehre zu Phase 0 zurück falls Start abgebrochen wurde
		continue
	#Phase 3: Start in einer Minute, schalte die Scheinwerfer an
	phase = 3
	spotlight()

	waitForT(7, 0.1)	#Warte bis zur nächsten Phase
	if end == True:	#Kehre zu Phase 0 zurück falls Start abgebrochen wurde
		continue
	#Phase 4: Start in 7 Sekunden, spiel Musik ab
	phase = 4
	GPIO.output(15, GPIO.LOW)
	track.play()

	waitForT(3, 0.1)	#Warte bis zur nächsten Phase
	if end == True:	#Kehre zu Phase 0 zurück falls Start abgebrochen wurde
		continue
	#Phase 5: Start in 3 Sekunden, "zünde" die Triebwerke
	phase = 5
	engine.start()

	while not(phase == 6):
		time.sleep(1)
	#Start der Rakete
	engineFadeout()
