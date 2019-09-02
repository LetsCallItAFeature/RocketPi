######################################################################################################
#	Die Darstellung erfolgt auf einem 16x2 LCD character-Display für die Informationen
#	und einem 4-stelligen 7-Segment-Display mit zentralem Doppelpunkt und I2C Backpack für Zeiten
#	und den Countdown.
#
#	Version mit englischen Kommentaren folgt bald
#	English version coming soon
#
#	Autor: Kai Arnetzl
######################################################################################################

#importiere alle benötigten Module
import requests
import json
import threading
import time
import random
#import pygame
from datetime import datetime
import RPi.GPIO as GPIO
from RPLCD import CharLCD
from Adafruit_LED_Backpack import SevenSegment
#deklariere alle benötigten globalen Variablen
GPIO.setmode(GPIO.BCM)
#GPIO.setwarnings(False)
#GPIO.setup(14,GPIO.OUT)
#GPIO.setup(17,GPIO.OUT)
segment = SevenSegment.SevenSegment() #initialisiert Siebensegmentdisplay mit Standardadresse
lcd = CharLCD(cols=16, rows=2, pin_rs=4, pin_e=17, pins_data=[18,22,23,24],numbering_mode = GPIO.BCM) #initialisiert LDC Display mit verwendeten Pins
launchtime = 0 #Unixtimestamp des nächsten Starts
end = True #Wurde Start abgesagt/ ist Mission zuende? (egal ob erfolgreich oder nicht)
phase = 0 #aktuelle Phase des Starts
mode = 0
data = {}
colon = True #Zustand des Doppelpunktes auf dem 7 Segment Display
engineLED = GPIO.PWM(14, 100) #Pin der Triebwerks-Leds
spotLED = GPIO.PWM(18, 100) #Pin der Scheinwerfer-Leds
GPIO.setup(15, GPIO.OUT)
GPIO.output(15, GPIO.HIGH)
segment.begin()
pygame.init()
track = pygame.mixer.Sound('Rocket Start Track.wav')

class button:
	def __init__(self, pin, led_pin = 0, debounce = 0.05, long_press = 0.5):
		self.pin = pin
		self.led_pin = led_pin
		self.debounce = debounce
		self.long_press = long_press
		self.state = 0
		self.led_state = False
		self.blinking = False
		GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.add_event_detect(self.pin, GPIO.FALLING, callback=self.callback_event, bouncetime = 50)
		if self.led_pin > 0:
			GPIO.setup(self.led_pin, GPIO.OUT)
			GPIO.output(self.led_pin, GPIO.LOW)

	def callback_event(self, channel):
		start_time = time.time()
		while GPIO.input(channel) == 0:
			time.sleep(0.01)
		buttonTime = time.time() - start_time
		if self.debounce <= buttonTime < self.long_press:
			self.state = 1
		elif self.long_press <= buttonTime:
			self.state = 2

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

	def blinkLed(self, period):
		if self.blinking == False:
			self.blinking = True
			blink = threading.Thread(target=self.blink_function, args=(period,), daemon = True)
			blink.start()

	def blink_function(self, period):
		og_state = self.led_state
		while og_state == self.led_state:
			GPIO.output(self.led_pin, GPIO.HIGH)
			time.sleep(period/2)
			GPIO.output(self.led_pin, GPIO.LOW)
			time.sleep(period/2)
		self.setLed(self.led_state)
		self.blinking = False

orange = button(20,21)
black_left = button(26)
black_right = button(19)
green = button(16)
def buttons():
	while True:
		status1 = orange.readStatus()
		if status1 == 1:
			#do stuff
		elif status == 2:
			#do stuff
		status2 = black_left.readStatus()
		if status2 == 1:
			#do stuff
		elif status2 == 2:
			#do stuff
		status3 = black_right.readStatus()
		if status3 == 1:
			#do stuff
		elif status3 == 2:
			#do stuff
		status4 = green.readStatus()
		if status4 == 1:
			#do stuff
		elif status4 == 2:
			#do stuff

def rocketengines():	#Flackern der Leds in den Triebwerken
	engineLED.start(0)
	for b in range(0,60):	#Für 3 Sekunden wird geflacker immer heller
		engineLED.ChangeDutyCycle(random.uniform(0,b))
		time.sleep(0.05)
	while phase == 5:	#Flackern während des Restes der Phase 5 mit voller maximaler Helligkeit
		engineLED.ChangeDutyCycle(random.uniform(30,100))
		time.sleep(0.05)

def engineFadeout():	#Leds in den Triebwerken glühen für ~10 Sekunden aus
	for b in range(0,61):
		engineLED.ChangeDutyCycle(60 - i)
		time.sleep(0.15)

def spotlight():	#Anschalten der Scheinwerfer
	for b in range(0,100):	#Scheinwerfer werden für 50 Sekunden immer heller
		spotLED.ChangeDutyCycle(b)
		time.sleep(0.5)
	#spotLED.on() 	#Scheinwerfer werden auf voller Helligkeit angelassen

def updatethread():	#Startzeit der nächsten Rakete wird ständig aus dem Internet gelesen und aktualisiert
	global launchtime
	global end
	global data
	while True:
		r = requests.get("https://launchlibrary.net/1.4/launch/next/1")	#Anfrage an Web-API, erhält JSON-Datei zurück
		data = r.json() #Wandel JSON in dictionary um
		status = (data["launches"][0]["status"])	#Auslesen des Status des nächsten Starts
		if status == 1:		#Status 1 = Startzeit der Rakete steht fest und Rakete hat GO
			launchtime = (data["launches"][0]["netstamp"])	#Startzeit wird ausgelesen und aktualisiert
			end = False
		elif status == 2 or status == 5:	#Status 2 = Startzeit nicht festgelegt oder Rakete hat NO GO, Status 5 = Start pausiert
			end = True	#Abbruch Startsequenz
		if phase == 5:
			isPhase6(status)
		if phase > 1:
			time.sleep(20)	#Ab Phase 2: Aktualisiere alle 20 Sekunden
		else:
			time.sleep(60)	#Vor Phase 2: Warte 1 Minute bis zum erneuten Aktualisieren

def isPhase6(status):
	if status == 3 and phase > 0:		#Status 3 = Mission erfolgreich
		display("SUCCSESS!"," ")
		end = True
	elif status == 4 and phase > 0:		#Status 4 = Start fehlgeschlagen
		display("FAILURE"," ")
		end = True
	elif status == 7 and phase > 0:		#Status 7 = Teilweiser Fehlschlag (z.B. nicht-stabiler Orbit)
		display("PARTIAL","FAILURE")
		end = True
	elif (time.time() - launchtime) > 3598:	#Timeout; nach 60 Minuten wird Start als abgeschlossen angesehen
		display("TIMEOUT", " ")
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
		oldTime = int(time.time())
		display(name, lsp)	#Zeige für 10 Sekunden Name der Rakete & Mission und Launch Service Provider
		while int(time.time()) < (oldTime+10):
			time.sleep(0.1)
		oldTime = int(time.time())
		display(mission, launchpad)	#Zeige für 10 Sekunden Art der Mission und Start

def display(line1, line2):	#Stelle 2 Zeilen auf LCD Display dar. Scrolle falls nötig.
	lcd.clear()
	length = len(line1)
	if len(line2) > length:	#Wie lang ist der längste String?
		length = len(line2)
	if len(line1) <= 16:	#Schreib Zeile 1 auf LCD falls diese komplett passt (maximale Länge ist 16 Zeichen)
		lcd.cursor_pos = (0,0)
		lcd.write_string(line1)
	if len(line2) <= 16:	#Schreib Zeile 2 auf LCD falls diese komplett passt (maximale Länge ist 16 Zeichen)
		lcd.cursor_pos = (1,0)
		lcd.write_string(line2)
	if length > 16:		#Falls eine Zeile länger als 16 Zeichen ist...
		for i in range(length - 15):
			if len(line1) > 16 and len(line1) >= i + 16:	#Falls Zeile 1 zu lang ist, scrolle diese
				lcd.cursor_pos = (0,0)
				lcd.write_string(line1[i:i+16])
			if len(line2) > 16 and len(line2) >= i + 16:	#Falls Zeile 2 zu lang ist, scrolle diese
				lcd.cursor_pos = (1,0)
				lcd.write_string(line2[i:i+16])

			if i == 0:	#Warte 1 Sekunde bevor gescrollt wird, scrolle anschließend mit 0,4 Sekunden/Zeichen
				time.sleep(1)
			else:
				time.sleep(0.4)
		time.sleep(1)

def getInfo():	#erhalte Informationen zum Start von Web-API
	try:
		name = (data["launches"][0]["name"])	#lies Namen der Rakete & Mission ab
		launchpad = (data["launches"][0]["location"]["name"])	#lies Ort der Startrampe ab
		mission = (data["launches"][0]["missions"][0]["typeName"])	#lies Art der Mission (z.B. Kommunikation) ab
		lsp = (data["launches"][0]["lsp"]["name"])	#lies Name des Launch Service Providers (z.B. NASA) ab
		return (name, launchpad, mission, lsp)
	except:
		return (" "," "," "," ")

def displaytime():
	colon = True	#Doppelpunkt auf Display ist dauerhaft an
	segmentClock(datetime.fromtimestamp(launchtime).strftime('%H%M'))	#Stelle die Startzeit der Rakete in der eingestellten Zeitzone auf dem 7 Segment Display dar

def waitForT(t, freq):	#Warte bis die Zeit bis zum Start t Sekunden beträgt mit einer Genauigkeit von freq Sekunden
	while launchtime - int(time.time()) > t:
		time.sleep(freq)
		if end == True:	#Hör auf zu warten falls Start abgebrochen wurde
			break

updatelaunch = threading.Thread(target=updatethread)
info = threading.Thread(target=displayInfo)
countdown = threading.Thread(target=countdownthread)
updatelaunch.start()	#Fang an, Startzeit und Status regelmäßig zu aktualisieren
display("Starting"," ")
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
