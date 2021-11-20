#!/usr/bin/python
# coding: utf-8
##picameraによる静止画撮影プログラム
##使い方：$ python raspi_picamera_capture_v1.0.py

import picamera        #picameraモジュールの呼び出し
import datetime as dt  #datetimeモジュールの呼び出し
import time            #timeモジュールの呼び出し

camera = picamera.PiCamera(resolution=(320, 240))  #解像度320X240 24frame/s
#camera.start_preview()  #プレビュー表示
#camera.hflip = True     ＃水平反転
#camera.vflip = True     #垂直反転
#camera.exposure_mode = 'night'  #露出モード

#画像に撮影日時を表示
camera.annotate_text_size = 16
camera.annotate_text = dt.datetime.now().strftime('%Y.%m.%d %H:%M:%S')
#camera.annotate_background = picamera.Color('black')  #日時の文字の背景色

for i in range(1,2400):  #静止画3600個分取得のため
    #camera.capture('/home/pi/picamera/a.jpg' % i)  #静止画を撮影
    dir_name = dt.datetime.now().strftime('%Y%m%d_%H:%M:%S')
    dir_path = '/home/pi/picamera/'+dir_name
    camera.capture(dir_path+'_%02d.jpg' % i)
    time.sleep(0.3)  #1秒毎に静止画を撮影するため
