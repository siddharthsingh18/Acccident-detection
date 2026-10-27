import socket
import imagezmq
import cv2
import time
from pathlib import Path
sender = imagezmq.ImageSender(connect_to='tcp://localhost:5555')

sender_name = socket.gethostname() # send your hostname with each image

default_img = Path(__file__).resolve().parent.parent / "notfound.png"
image = cv2.imread(str(default_img))
print(image)
print(sender_name)
s = time.time()
sender.send_image(sender_name, image)
e = time.time()
print('it took- ', e-s, ' sec')