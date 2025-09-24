"""
Fresno Ideaworks Raspberry Pi photobooth for Maker Faire 2025.
J. Daniel Ozeran dano@fresnoideaworks.org
9/23/2025
Button controls the shutter, runs a countdown and takes the pictures.
Takes pictures and merges with overlay.  Image is "flattened" and saved using a dynamic filename.
Once files are saved, a random message is selected and images are uploaded to
a selection of social media sites.
"""
from auth import INSTA_ID, INSTA_KEY, SKY_ID, SKY_KEY
from gpiozero import Button
import os
from pathlib import Path
from instagrapi import Client as IClient           # Instagram client is IClient
from atproto import Client as BClient  # BlueSky library also uses BClient 
from atproto import models
from datetime import datetime, timedelta
from PIL import Image
from time import localtime, gmtime, strftime, sleep
import time
import schedule
import logging
import cv2
from picamera2 import Picamera2, Preview, MappedArray
from PIL import Image
import numpy as np
import random
from signal import pause

logger = logging.getLogger('photobooth')
logging.basicConfig(level=logging.INFO)
logger.info("starting")
dirpath=Path.cwd()
overlay_path = str(dirpath)+"/overlays"
photo_path = str(dirpath)+"/photos"
Button.was_held = False
button = Button(17,hold_time=5)
#messages = ["We're having fun at MakerFaire", "Check us out here with Fresno Ideaworks", "Makers make cool stuff"] # You can use either.  Using a file makes updates easier.
messages=[]
with open('message.txt', mode='r') as f:
   for lines in f:
        line = lines.rstrip()  # remove the newline character
        messages.append(line)  # add the line in the list

camera = Picamera2()
# Configure for still capture
capture_config = camera.create_still_configuration(main={"size": (1024, 768)})
# Configure for previews
preview_config = camera.create_preview_configuration()
# Apply preview configuration
camera.configure(preview_config)

# Adding size format to preview call to roughly fill screen on 7" 1024x600 display.
#camera.start_preview(Preview.QTGL, x=0, y=32, width=1024, height=540)
#camera.start() #show_preview=True)

# The path to your transparent PNG frame
overlay_image1 = overlay_path+"/MakerFaireOverlay.png"
overlay_image2 = overlay_path+"/MakerFaireOverlay2.png"
overlay_list = [] # Filenames ["MakerFaireOverlay.png", "MakerFaireOverlay2.png"] (etc.)
overlays = [] #storage of the actual overlay Images.

"""
Function Definitions
"""

def get_message():
    return random.choice(messages)


#overlay_list = [] # ["MakerFaireOverlay.png", "MakerFaireOverlay2.png"] (etc.)
def load_overlay_names():
    path_to_overlays  = Path(overlay_path)
    overlay_list = list(path_to_overlays.glob("*.png"))
    for i in range(len(overlay_list)):
        overlay_list[i]=overlay_list[i].name
    overlay_list.sort()
    return overlay_list

def load_overlays():
    ol = []
    for i in range(len(overlay_list)):
        ol.append(cv2.cvtColor(np.array(Image.open(overlay_path+"/"+overlay_list[i])),cv2.COLOR_RGB2RGBA))
    return ol

def quit():
    logger.info("quitting")
    camera.stop_preview()
    camera.stop()
    
def capture_photos(n):
    """
    Capture n photos in sequence and return a list of file paths
    """
    photos = []
    for pic in range(n):
        sleep(1)
        countdown(4)
        logger.info("capturing photo "+str(pic+1))
        photo = _gen_filename()
        job = camera.switch_mode_and_capture_file(capture_config, photo, wait=True)
        #photo = camera.capture_image()
        logger.info("captured photo: {}".format(photo))
        apply_overlay_to_image_file(photo,4)
        photos.append(photo)
    return photos

def countdown(n):
    logger.info("running countdown")
    for i in reversed(range(n)):
        camera.set_overlay(overlays[i])
        print(i+1)
        sleep(1)
    camera.set_overlay(overlays[6])
        
def _gen_filename():
    """
    Generate a filename with a timestamp
    """
    filename = strftime(str(dirpath)+"/photos/photo-%d-%m %H:%M:%S.png", time.localtime())
    return filename

def _pad(resolution, width=32, height=16):
    # A little utility routine which pads the specified resolution
    # up to the nearest multiple of *width* and *height*; this is
    # needed because overlays require padding to the camera's
    # block size (32x16)
    return (
        ((resolution[0] + (width - 1)) // width) * width,
        ((resolution[1] + (height - 1)) // height) * height,)


def apply_overlay_to_image_file(output,overlay): # (output is the filename, overlay is the INDEX to the overlay_list).
    output_img = Image.open(output).convert('RGBA')
    # re-open output with Image to add alpha channel.
    new_output = Image.alpha_composite(output_img, Image.open(overlay_path+"/"+overlay_list[overlay]).convert("RGBA"))
    new_output.save(output)
    return output

def convert_png_to_jpeg(png_photos):  #png_photos is a list of filenames
                                      #Converts PNG images to JPEG for upload.
   jpg_photos = []
   for pic in range(len(png_photos)):
      png_img = cv2.imread(png_photos[pic],cv2.IMREAD_UNCHANGED)
      jpg_img = str(png_photos[pic][:-4]+".jpg")
      cv2.imwrite(jpg_img,png_img,[int(cv2.IMWRITE_JPEG_QUALITY),100])
      jpg_photos.append(jpg_img)
   return jpg_photos

def login_insta_user(user=INSTA_ID,key=INSTA_KEY):
     cl = IClient()
     cl.login(user, key)
     logger.info("Successfully logged into Instagram.")
     return cl

def Insta_upload(client, media, message = "Hello from @FresnoIdeaworks"):
    try:
        if client: # client is present and presumably logged in.
            logger.info("Logged in and uploading to Instagram. ")
            client.album_upload(media, message, extra_data={"custom_accessibility_caption": "alt text example", "like_and_view_counts_disabled": 1, "disable_comments": 0,})
        else: 
            logger.info("Client error for Instagram.")
    except NameError:
       logger.info("Client variable does not exist or is not active. ")

def login_bluesky_user(user=SKY_ID,key=SKY_KEY):
     cl = BClient()
     cl.login(user, key)
     logger.info("Successfully logged into BlueSky.")
     return cl


def bluesky_upload(client, media, message="Hello from @FresnoIdeaworks"):
    try:
        if client: # client is present and presumably logged in.
            aspects=[]
            for i in range(len(media)):
                aspects.append(models.AppBskyEmbedDefs.AspectRatio(height=768, width=1024))
            images = []
            for path in media:
                with open(path, 'rb') as f:
                    images.append(f.read())
            logger.info("Logged in and uploading to BlueSky. ")
            client.send_images(text=message, images=images, image_aspect_ratios=aspects,)
        else: 
            logger.info("Client error for BlueSky.")
    except NameError:
       logger.info("Client variable does not exist or is not active. ")
    
"""
Button callback functions
"""
def shutdown_script():
   # Button was held for more than 10 seconds, so shut down the system.
    button.was_held = True
    print("Button held! Shutting down script...")
    logger.info("quitting")
    camera.stop_preview()
    camera.stop()
    sleep(2) 
    os._exit(0) # This works.
"""
Where the Magic Really Happens
"""

def released(btn):
    if not btn.was_held:
        pressed()
        # Here's where any activity should be performed on button presses.
        # take photos
        photos = []
        photos = capture_photos(3)
        # reformat photos
        jpg_images=[]
        jpg_images = convert_png_to_jpeg(photos)
        # upload photos
        message = random.choice(messages)
        #message = "Testing the #FresnoIdeaworks photobooth for #MakerFaireBayArea 2025"
        #Insta_upload(IClient, jpg_images, message)
        #bluesky_upload(BClient, jpg_images, message)
    btn.was_held = False

def pressed():
    pass
    print("button was pressed not held")
    #This can be an empty function.



"""
End of Function Defnitions
"""
"""
System Initialization
"""
# Start the preview and camera
# Adding size format to preview call to roughly fill screen.
camera.start_preview(Preview.QTGL, x=0, y=32, width=1024, height=540)
camera.start() #show_preview=True)
overlay_list=load_overlay_names()
overlays=load_overlays()
camera.set_overlay(overlays[6])

# Create clients for Instagram and BlueSky.
IClient = login_insta_user(INSTA_ID,INSTA_KEY)
BClient = login_bluesky_user(SKY_ID,SKY_KEY)
# Assign button function callbacks.
button.when_released = released # Button was pressed and THEN released.
button.when_held = shutdown_script
"""
End of Initialization
"""
"""
pause()
Main Program Code (I think)
"""
pause()

