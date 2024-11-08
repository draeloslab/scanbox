
import sys
# sys.path.append("C:")
sys.path.append("C:\\Users\\User\\bruker2p_control") 

import examples.Bunnies
import time
import threading
import numpy as np
from ctypes import *
import os
from pynput import keyboard
import cv2
import array
import zmq
from streaming import Stream_Buffer
import json
from json import JSONEncoder
from examples import Bunnies
import platform

if platform.system() == "Windows":
    import win32com.client




HOST_IP = '*' #'127.0.0.1'#'10.196.159.238'
PORT = '50154'

class NumpyArrayEncoder(JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return JSONEncoder.default(obj)

class ZMQ_Streamer():
    def __init__(self, pl):
        
        self.pl = pl
        # self.pl = win32com.client.Dispatch("PrairieLink.Application")
        # self.pl.Connect()
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.resetBuffer = False

        self.socket.bind("tcp://{}:{}".format(HOST_IP, PORT))
        print(f'Starting movie streaming server on port {PORT} sending images on {HOST_IP}' + (
            ' (localhost)' if HOST_IP == '127.0.0.1' else ''))
    def keyboard_input(self, key):
        try:
            if (key.char == 'q'):
                self.pl.SendScriptCommands('-Abort')
                self.pl.Disconnect()
                return (False)

            if (key.char == 'd'):
                self.resetBuffer = True

            if (key.char == 'z'):
                self.pl.sendScriptCommands('-Abort')
                time.sleep(0.25)
                self.pl.sendScriptCommands('-lv')

        except:
            pass

    def initialize_keyboard_control(self):
        self.listener =  keyboard.Listener(on_press=lambda event: self.keyboard_input(event))
        self.listener.start()
        self.listener.join()

    def low_level_stream(self, quality):
        # set the save path to the recycle bin
        self.pl.SendScriptCommands('-SetSavePath E:/Trash')
        # set some variables to help image decoding
        pixels_per_line = self.pl.PixelsPerLine()
        lines_per_frame = self.pl.LinesPerFrame()
        # enable streaming raw data
        self.pl.SendScriptCommands('-StreamRawData True')
        # start streaming live
        self.pl.SendScriptCommands('-lv')
        samples_per_pixel = self.pl.SamplesPerPixel()
        print(pixels_per_line, lines_per_frame, samples_per_pixel)

        frame_size = pixels_per_line * lines_per_frame * samples_per_pixel

        myBuffer = Stream_Buffer.BufferHandler(frame_size * 6, frame_size, self.pl, overwrite=True, event_driven=True)


        myBuffer.run_buffer()
        time.sleep(0.033)
        if(quality == 'low'):
            t2 = threading.Thread(target=self.event_publish_loop, args=[myBuffer], daemon=True)
        elif(quality == 'high'):
            t2 = threading.Thread(target=self.event_publish_loop_full, args=[myBuffer], daemon=True)

        print("Start thread")

        t2.start()

    def event_publish_loop(self, bufferHandler):

        zz = 0
        cumtime = 0
        sstart = time.time()
        start_time = 0
        maxBright = 0
        minBright = 0
        diff = 1

        frame_ready = bufferHandler.get_frame_flag()
        while True:
            time.sleep(9)
            #wait until a full frame is ready in the buffer
            #print("wait frame")
            frame_ready.wait()
            try:
                print(time.time() - last_frame_time)
                if(time.time() - last_frame_time > 500 or self.resetBuffer):
                    bufferHandler.flush_and_reset()
                    last_frame_time = None
                    self.resetBuffer = False
                else:
                    last_frame_time = time.time()
            except Exception as e:
                print(e)
                pass
            #print("got frame")
            #clear the flag that a frame is ready as soon as we start processing this frame
            myFrameAddress, buffer = bufferHandler.get_frame_address_event()

            # this function efficiently gets three arrays corresponding to one sample for every pixel in the frame
            # there are 3 samples per pixel so this is three frames worth of samples
            # for speed these are separate 1-d arrays and not one 2-d array
            thinga = np.array(buffer[myFrameAddress:myFrameAddress + 786432:3])
            thingb = np.array(buffer[myFrameAddress + 1: myFrameAddress + 786432:3])
            thingc = np.array(buffer[myFrameAddress + 2: myFrameAddress + 786432:3])
            bufferHandler.lock.release()

            # this takes the mean of each of the three samples for each pixel, giving us a 1-d array with as many
            # samples as there are pixels in each image
            try:
                nextthing = np.mean([thinga, thingb, thingc], axis=0)
            except:
                bufferHandler.flush_and_reset()
                last_frame_time = None
                continue

            # this flips every other row, creating a 2-d list where each element is one row of pixel values in the
            # correct orientation
            flippedthing = nextthing #[nextthing[i:i + 512] if (i / 512) % 2 else nextthing[i:i + 512][::-1] for i in
                            #range(0, 262144, 512)]

            # this turns the array into unsigned 8-bit ints for broadcast
            finalthing = np.array(flippedthing, np.uint8)

            self.socket.send_multipart([
                "type".encode(),
                "bruker_img".encode(),
                "data".encode(),
                finalthing.tobytes()
            ])

            zz = zz + 1

            # this loop calculates frame rate
            if (not (zz % 300)):

                print("Average frame rate published:", zz / (time.time() - sstart))


    def event_publish_loop_full(self, bufferHandler):
        zz = 0
        cumtime = 0
        sstart = time.time()
        start_time = 0
        maxBright = 0
        minBright = 0
        diff = 1
        last_frame_time = None

        frame_ready = bufferHandler.get_frame_flag()
        while True:
            #time.sleep(9)
            #wait until a full frame is ready in the buffer
            frame_ready.wait()

            try:
                #print(time.time() - last_frame_time)
                if (time.time() - last_frame_time > 0.5 or self.resetBuffer):
                    bufferHandler.flush_and_reset()
                    last_frame_time = None
                    self.resetBuffer = False
            except Exception as e:
                print(e)
                pass
            last_frame_time = time.time()

            #clear the flag that a frame is ready as soon as we start processing this frame
            myFrameAddress, buffer = bufferHandler.get_frame_address_event()

            # this function efficiently gets three arrays corresponding to one sample for every pixel in the frame
            # there are 3 samples per pixel so this is three frames worth of samples
            # for speed these are separate 1-d arrays and not one 2-d array
            # thinga = np.array(buffer[myFrameAddress:myFrameAddress + 131072:2]) #786432:3])
            # thingb = np.array(buffer[myFrameAddress + 1: myFrameAddress + 131072:2])
            # thingc = np.array(buffer[myFrameAddress + 2: myFrameAddress + 786432:3])
            thinga = np.array(buffer[myFrameAddress:myFrameAddress + 262144])
            # print(thinga.shape)
            bufferHandler.lock.release()

            # this takes the mean of each of the three samples for each pixel, giving us a 1-d array with as many
            # samples as there are pixels in each image
            try:
                nextthing = thinga #np.mean([thinga, thingb], axis=0)
            except:
                bufferHandler.flush_and_reset()
                last_frame_time = None
                continue

            # this flips every other row, creating a 2-d list where each element is one row of pixel values in the
            # correct orientation
            flippedthing = [nextthing[i:i + 512] if (i / 512) % 2 else nextthing[i:i + 512][::-1] for i in
                            range(0, 262144, 512)]

            finalthing = np.array(flippedthing)
            numpyData = {"array": finalthing}

            #print("SEND")
            self.socket.send_pyobj(dict({
                "type": "bruker_img",
                "data": finalthing
            }))

            # self.socket.send_multipart([
            #     "type".encode(),
            #     "bruker_img".encode(),
            #     "data".encode(),
            #     jsonified
            # ])


            zz = zz + 1

            # this loop calculates frame rate
            if (not (zz % 300)):

                print("Average frame rate published:", zz / (time.time() - sstart))


    def event_display_loop_debug(self, bufferHandler):
        cv2.namedWindow("Image")
        zz = 0
        cumtime = 0
        sstart = time.time()
        start_time = 0
        maxBright = 0
        minBright = 0
        diff = 1

        frame_ready = bufferHandler.get_frame_flag()
        while True:
            # wait until a full frame is ready in the buffer
            frame_ready.wait()
            # clear the flag that a frame is ready as soon as we start processing this frame
            myFrameAddress, buffer = bufferHandler.get_frame_address_event()

            # this function efficiently gets three arrays corresponding to one sample for every pixel in the frame
            # there are 3 samples per pixel so this is three frames worth of samples
            # for speed these are separate 1-d arrays and not one 2-d array
            thinga = np.array(buffer[myFrameAddress:myFrameAddress + 786432:3])
            thingb = np.array(buffer[myFrameAddress + 1: myFrameAddress + 786432:3])
            thingc = np.array(buffer[myFrameAddress + 2: myFrameAddress + 786432:3])
            bufferHandler.lock.release()

            # this takes the mean of each of the three samples for each pixel, giving us a 1-d array with as many
            # samples as there are pixels in each image
            nextthing = np.mean([thinga, thingb, thingc], axis=0)

            # this flips every other row, creating a 2-d list where each element is one row of pixel values in the
            # correct orientation
            flippedthing = [nextthing[i:i + 512] if (i / 512) % 2 else nextthing[i:i + 512][::-1] for i in
                            range(0, 262144, 512)]

            # this turns the array into unsigned 8-bit ints for display
            # finalthing = np.array(flippedthing, np.uint8)

            # this code first normalizes the pixel brightness between 0 and 255 before turning it into 8-bit ints for display
            # this looks better but is not necessary for sending the data to other applications
            finalthing = np.array((np.array(flippedthing) - minBright) / diff * 255, np.uint8)

            # Gif(not(zz%10)):
            # this uses the cv2 library to display the final image
            cv2.imshow("Image", finalthing)
            # print(bufferHandler.read_head/bufferHandler.frame_size, bufferHandler.write_head/bufferHandler.frame_size)
            cv2.waitKey(1)

            zz = zz + 1

            # this loop calculates frame rate and normalization parameters every 300 frames
            if (not (zz % 300)):
                # arbitrarily choose the max and min brightness values from every 300th frame as normalization params
                maxBright = max(nextthing)
                minBright = min(nextthing)
                diff = maxBright - minBright

                #
                print("Average frame rate sent by publisher:", zz / (time.time() - sstart))
                # print(maxBright, minBright, diff)
                # print(bufferHandler.samples_written, bufferHandler.samples_read, (bufferHandler.samples_written-bufferHandler.samples_read)/bufferHandler.frame_size)
                # print(bufferHandler.buffer.buffer_info())


if __name__ == "__main__":
    #import win32com.client

    #pl_obj = win32com.client.Dispatch("PrairieLink.Application")
    #pl_obj.Connect()


    my_pl = win32com.client.Dispatch("PrairieLink.Application")

    # my_pl = examples.Bunnies.BunnyStreamer()

    my_pl.Connect()
    myStreamer = ZMQ_Streamer(my_pl)
    myStreamer.low_level_stream('high')
    myStreamer.initialize_keyboard_control()