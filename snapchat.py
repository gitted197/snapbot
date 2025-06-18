from ppadb.client import Client as AdbClient
from PIL import Image, ImageDraw, ImageFont
import pyautogui
import time
from datetime import datetime
import subprocess
import PySimpleGUI as sg
from pyscreeze import pixel
sg.theme("reddit")
#sg.Window(title="Hello World", layout=[[]], margins=(100, 50)).read()
 
interface_column1 = [
        [sg.Text("Recipient username (case sensitive!)")],
        [sg.In(size=(20, 1), key='-INPUTUSERNAME-')],
        [sg.Text("Amount of points to generate:")],
        [sg.In(size=(20, 1), key='-INPUTPOINTS-')],
        [sg.Text("Your phone type:")],
        [sg.Radio('Google Pixel 5', "phonetype", default=True, key='-PIXEL5-')],
        [sg.Radio('Other', "phonetype", default=False, key='-OTHERPHONE-')],
        [sg.Button('Start'), sg.Button('Exit')]
] 

interface_column2 = [
        [sg.Multiline(key='-LOG-', autoscroll='true', background_color='black', text_color='yellow', size=(45,15))]
]

# ----- Full layout -----
layout = [
    [
        sg.Column(interface_column1),
        sg.VSeperator(),
        sg.Column(interface_column2)
    ]
]

window = sg.Window('SnapGen', layout, margins=(35, 25))    


while True:
    event, values = window.read()
    if event == "Exit" or event == sg.WIN_CLOSED:
        break  


    def inputNumber(points_input):
        try:
            isinstance(points_input, int)
            #userInput = int()
            #points_input = int()
        except ValueError:
            print("Please enter a number.")
        else:
            #return userInput
            #return points_input
            return points_input

    def logTime():
        currenttime = datetime.now()
        hour = str(currenttime.hour)
        minute = str(currenttime.minute)
        second = str(currenttime.second)

        logtimeoutput = hour + ":" + minute + ":" + second + " - "
        return logtimeoutput

    log = window['-LOG-']

    username_input = values['-INPUTUSERNAME-']  
    print(username_input)
    points_input = values['-INPUTPOINTS-']
    generate_amount = inputNumber(points_input)
    print(generate_amount)
    generate_amount_int = int(generate_amount)

    def voorbeeldlog(log, window, x):
        log.update(log.get()+"\n" + logTime() + str(x))
        window.update()

    if values['-OTHERPHONE-'] == True:
        log.update(log.get()+"\n" + logTime() + "Google Pixel 5 is currently the only supported device. Contact me for further support on new devices.")
        window.refresh()
        continue

    if values['-PIXEL5-'] == True:
        #Array for all phones. Array is built up as follows: circle, yellowsend, bluesend, camera
        pixel_array = ["539", "1999", "998", "2224", "999", "2206", "540", "2219"]
        log.update(log.get()+"\n" + logTime() + "Set pixels to Google Pixel 5")
        window.refresh()

    cameraneedle = Image.open('Snapchat/camera.png')
    circleneedle = Image.open('Snapchat/circle.png')
    yellowneedle = Image.open('Snapchat/sendto_pixel.png')
    senditneedle = Image.open('Snapchat/sendneedle.png')
    #Usernameneedle = created after username has been filled by user

    #Create ADB connection to phone
    log.update(log.get()+"\n" + logTime() + "Starting ADB server to connect phone")
    window.refresh()
    adbStart = subprocess.Popen(['Snapchat/adb', 'start-server'])
    log.update(log.get()+"\n" + logTime() + "ADB started")
    window.refresh()
    time.sleep(3)
    log.update(log.get()+"\n" + logTime() + "Connecting to ADB server")
    window.refresh()
    adb = AdbClient(host='127.0.0.1', port=5037)
    log.update(log.get()+"\n" + logTime() + "ADB server connected")
    window.refresh()
    #List devices
    log.update(log.get()+"\n" + logTime() + "Getting devices")
    window.refresh()
    devices = adb.devices()
    log.update(log.get()+"\n" + logTime() + "Got devices")
    window.refresh()
    #Connect device
    log.update(log.get()+"\n" + logTime() + "Connecting to device")
    window.refresh()
    device = devices[0]
    log.update(log.get()+"\n" + logTime() + "Device connected")
    window.refresh()


    #Generating username picture to compare with screenshot
    #300x60px white image
    img = Image.new('RGB', (650, 60), color = (255, 255, 255))
    #Avenir font, size 35
    fnt = ImageFont.truetype('include/AvenirRegular.ttf', 45)
    d = ImageDraw.Draw(img)
    #Account gets passed into text on previously created image, fill black
    d.text((10,0), username_input, font=fnt, fill=(0, 0, 0))
    #Saving image
    img.save('Snapchat/usernameneedle.png')

    log.update(log.get()+"\n" + logTime() + "User wants to generate " + generate_amount + " Snapchat points. They will be sent to " + username_input + ". Here we go!")
    window.refresh()

    #Waking up device
    log.update(log.get()+"\n" + logTime() + "Waking up device")
    window.refresh()
    device.shell("input keyevent KEYCODE_WAKEUP")
    log.update(log.get()+"\n" + logTime() + "Swipe to unlock")
    window.refresh()
    device.shell("input swipe 550 2100 550 500")


    #Activating airplane mode
    #log.update(log.get()+"\n" + logTime() + "Enabling airplane mode")
    #window.refresh()
    #device.shell("settings put global airplane_mode_on 1")
    #device.shell("am broadcast -a android.intent.action.AIRPLANE_MODE")
    time.sleep(0.5)

    #Disabling wifi
    #log.update(log.get()+"\n" + logTime() + "Disabling Wi-Fi")
    #window.refresh()
    #device.shell("svc wifi disable")
    #time.sleep(0.5)

    #Killing, then booting, Snapchat
    log.update(log.get()+"\n" + logTime() + "Killing Snapchat, then rebooting it")
    window.refresh()
    device.shell("am force-stop com.snapchat.android")
    device.shell("am start com.snapchat.android")
    time.sleep(2)


    #Taking first picture
    #Screenshot for circle haystack
#    device.shell("screencap -p /sdcard/screen_circle_auto.png")
#    device.pull("/sdcard/screen_circle_auto.png", "Snapchat/screen_circle_auto.png")
#    circlehaystack = Image.open('Snapchat/screen_circle_auto.png')
    #circlehaystack = Image.open('Snapchat/screen_circle.png')
#    circletoploc = pyautogui.locate(circleneedle, circlehaystack, confidence=0.7)
#    circlex, circley = pyautogui.center(circletoploc)
#    print(f'Circle for this device is at X: {circlex}, Y: {circley}')
    circlex = pixel_array[0]
    circley = pixel_array[1]
    device.shell(f"input touchscreen tap {circlex} {circley}")
    time.sleep(2)


    #Screenshot for yellow haystack
#    device.shell("screencap -p /sdcard/screen_sendto_yellow.png")
#    device.pull("/sdcard/screen_sendto_yellow.png", "Snapchat/screen_sendto_yellow.png")
#    yellowhaystack = Image.open('Snapchat/screen_sendto_yellow.png')
#    yellowtoploc = pyautogui.locate(yellowneedle, yellowhaystack, confidence=0.7)
#    yellowx, yellowy = pyautogui.center(yellowtoploc)
#    print(f'Yellow for this device is at X: {yellowx}, Y: {yellowy}')
    yellowx = pixel_array[2]
    yellowy = pixel_array[3]
    device.shell(f"input touchscreen tap {yellowx} {yellowy}")
    time.sleep(1.5)

    #Screenshot for username haystack
    device.shell("screencap -p /sdcard/screen_usernames.png")
    device.pull("/sdcard/screen_usernames.png", "Snapchat/screen_usernames.png")
    usernamehaystack = Image.open('Snapchat/screen_usernames.png')
    usernameneedle = Image.open('Snapchat/usernameneedle.png')
    usernametoploc = pyautogui.locate(usernameneedle, usernamehaystack, confidence=0.7)
    if usernametoploc == False:
        log.update(log.get()+"\n" + logTime() + "Username not found. Please make sure it's in the list and try again.")
        window.refresh()
        break
    usernamex, usernamey = pyautogui.center(usernametoploc)
    print(f'Username for this device is at X: {usernamex}, Y: {usernamey}')
    device.shell(f"input touchscreen tap {usernamex} {usernamey}")
    time.sleep(0.5)

    #Max, fully send it.
#    device.shell("screencap -p /sdcard/screen_sendit.png")
#    device.pull("/sdcard/screen_sendit.png", "Snapchat/haystack_sendit.png")
#    sendithaystack = Image.open('Snapchat/haystack_sendit.png')
#    sendittoploc = pyautogui.locate(senditneedle, sendithaystack, confidence=0.9)
#    senditx, sendity = pyautogui.center(sendittoploc)
#    print(f'Send it for this device is at X: {senditx}, Y: {sendity}')
    senditx = pixel_array[4]
    sendity = pixel_array[5]
    device.shell(f'input touchscreen tap {senditx} {sendity}')
    time.sleep(0.5)

    #Back to camera screen
#    device.shell("screencap -p /sdcard/screen_camera.png")
#    device.pull("/sdcard/screen_camera.png", "Snapchat/haystack_camera.png")
#    camerahaystack = Image.open('Snapchat/haystack_camera.png')
#    cameratoploc = pyautogui.locate(cameraneedle, camerahaystack, confidence=0.9)
#    camerax, cameray = pyautogui.center(cameratoploc)
#    print(f'Camera for this device is at X: {camerax}, Y: {cameray}\n')
    camerax = pixel_array[6]
    cameray = pixel_array[7]
    device.shell(f'input touchscreen tap {camerax} {cameray}')


    snapssent = 1
    snapssent_log = str(snapssent)
    log.update(log.get()+"\n" + logTime() + "Snap number: ")
    window.refresh()
    currenttime = datetime.now()
    log.update(log.get()+"\n" + logTime() + snapssent_log)
    window.refresh()
    snapssent += 1
    snapssent_log = str(snapssent)
    time.sleep(2)

    #Going through another snap send to re-locate username, just in case the user wasn't on top of the 'recent' list.
    device.shell(f"input touchscreen tap {circlex} {circley}")
    time.sleep(1.5)
    device.shell(f"input touchscreen tap {yellowx} {yellowy}")
    time.sleep(1)

    #Screenshot 2 for username haystack    
    device.shell("screencap -p /sdcard/screen_usernames.png")
    device.pull("/sdcard/screen_usernames.png", "Snapchat/screen_usernames.png")
    usernamehaystack = Image.open('Snapchat/screen_usernames.png')
    usernameneedle = Image.open('Snapchat/usernameneedle.png')
    usernametoploc = pyautogui.locate(usernameneedle, usernamehaystack, confidence=0.7)
    if usernametoploc == False:
        log.update(log.get()+"\n" + logTime() + "Username not found. Please make sure it's in the list and try again.")
        window.refresh()
        break
    usernamex, usernamey = pyautogui.center(usernametoploc)
    print(f'Username 2 for this device is at X: {usernamex}, Y: {usernamey}')
    device.shell(f"input touchscreen tap {usernamex} {usernamey}")
    time.sleep(0.5)
    device.shell(f'input touchscreen tap {senditx} {sendity}')
    time.sleep(0.5)
    device.shell(f'input touchscreen tap {camerax} {cameray}')

    snapssent = 2
    snapssent_log = str(snapssent)
    log.update(log.get()+"\n" + logTime() + snapssent_log)
    window.refresh()
    snapssent += 1
    snapssent_log = str(snapssent)
    

    #Looping through the amount of points the user wants to generate
    count = 2
    while count < generate_amount_int:

        device.shell(f"input touchscreen tap {circlex} {circley}")
        time.sleep(1)
        device.shell(f"input touchscreen tap {yellowx} {yellowy}")
        time.sleep(1.7)
        device.shell(f"input touchscreen tap {usernamex} {usernamey}")
        device.shell(f'input touchscreen tap {senditx} {sendity}')
        time.sleep(1)
        device.shell(f'input touchscreen tap {camerax} {cameray}')
        log.update(log.get()+"\n" + logTime() + snapssent_log)
        window.refresh()
        count += 1  # This is the same as count = count + 1
        snapssent += 1
        snapssent_log = str(snapssent)

    log.update(log.get()+"\n" + logTime() + "Done sending snaps. Hopefully generated " + snapssent_log + " points.")
    window.refresh()
window.close()
