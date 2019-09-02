import requests
import json
import threading
import time
import random
from signal import pause
from datetime import datetime
from gpiozero import PWMLED
launchtime = 0
abort = True
phase = 0
engineLED = PWMLED(14)
spotLED = PWMLED(17)


def rocketengines():
	for b in range(0,60):
		engineLED.value = random.uniform(0,b/100)
		time.sleep(0.05)
	while phase == 5:
		engineLED.value = random.uniform(0.3,1)
		time.sleep(0.05)

def spotlight():
	for b in range(0,100):
		spotLED.value = b/100
		time.sleep(0.5)
	spotLED.on()

def updatethread():
	global launchtime
	global abort
	while True:
		r = requests.get("https://launchlibrary.net/1.4/launch/next/1")
		data = r.json()
		status = (data["launches"][0]["status"])
		if status == 1:
			launchtime = (data["launches"][0]["netstamp"])
			abort = False
		elif status == 2:
			abort = True
		elif status == 5:
			abort = True
		time.sleep(60)


def countdownthread():
	oldTime = time.time()
	while phase >= 2:
		rtime = int(time.time())
		if launchtime >= rtime:
			seconds = launchtime - rtime
		else:
			seconds = rtime - launchtime
		if rtime > oldTime:
			oldTime = rtime
			print (int(seconds/60)%60, 'min', seconds % 60, 's')
		time.sleep(0.1)


def displayInfo():
	oldTime = 0
	name, launchpad, mission, lsp = getInfo()
	while phase >= 1:
		while int(time.time()) < (oldTime+5):
			time.sleep(0.1)
		print (name)
		print (lsp)
		oldTime = int(time.time())
		while int(time.time()) < (oldTime+5):
			time.sleep(0.1)
		print (mission)
		print (launchpad)
		oldTime = int(time.time())

def getInfo():
	r = requests.get("https://launchlibrary.net/1.4/launch/next/1")
	data = r.json()
	name = (data["launches"][0]["name"])
	launchpad = (data["launches"][0]["location"]["name"])
	mission = (data["launches"][0]["missions"][0]["typeName"])
	lsp = (data["launches"][0]["lsp"]["name"])
	return (name, launchpad, mission, lsp)

def displaytime():
	print (datetime.fromtimestamp(launchtime).strftime('%H:%M'))

def waitForT(t, freq):
	while launchtime - int(time.time()) > t:
		time.sleep(freq)
		if abort == True:
			break

updatelaunch = threading.Thread(target=updatethread)
info = threading.Thread(target=displayInfo)
countdown = threading.Thread(target=countdownthread)
engine = threading.Thread(target=rocketengines)
updatelaunch.start()

while True:
	#Phase 0: wait for next launch
	phase = 0
	while launchtime - time.time() >= 18000 or abort == True:
		time.sleep(10)
		if abort == True:
			print ("konnte keine Startzeit erhalten/ TBD")
		else:
			print (">5 Stunden")
	#Phase 1: launch is between 5 and 1 hours away, display launch time and information
	phase = 1
	displaytime()
	info.start()

	waitForT(3600, 1)
	if abort == True:
		continue
	#Phase 2: launch is less than 1 hour away, start countdown
	phase = 2
	countdown.start()

	waitForT(60, 1)
	if abort == True:
		continue
	#Phase 3: launch is 1 minute away, light up the rocket
	phase = 3
	spotlight()

	waitForT(7, 0.1)
	if abort == True:
		continue
	#Phase 4: launch is 7 seconds away, start music
	phase = 4
	waitForT(3, 0.1)
	if abort == True:
		continue
	#Phase 5: launch is 3 seconds away, start rocket engines
	phase = 5
	engine.start()
	#Launch!!! (hopefully) Clock now shows T+
	#launch has finished or timeout, turn rocket engines off, stop displaying T+ and information, revert everything
