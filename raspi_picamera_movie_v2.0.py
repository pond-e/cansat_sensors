#!/usr/bin/python
# coding: utf-8
##picameraによる動画撮影プログラム
##使い方：$ python raspi_picamera_movie_v1.0.py

import picamera        #picameraモジュールの呼び出し
import datetime as dt  #datetimeモジュールの呼び出し

camera = picamera.PiCamera(resolution=(320, 240), framerate=24)  #解像度320X240 24frame/s
#camera.start_preview()  #プレビュー表示
#camera.hflip = True     ＃水平反転
#camera.vflip = True     #垂直反転
#camera.exposure_mode = 'night'  #露出モード

#画像に撮影日時を表示
camera.annotate_text_size = 16
camera.annotate_text = dt.datetime.now().strftime('%Y.%m.%d %H:%M:%S')
#camera.annotate_background = picamera.Color('black')  #日時の文字の背景色

dir_name = dt.datetime.now().strftime('%Y.%m.%d %H:%M:%S')
dir_path = '/home/pi/picamera/'+dir_name
camera.start_recording(dir_path+'movie_1.h264')    #撮影開始
start = dt.datetime.now()           #各々の動画の撮影開始時刻を保存
while (dt.datetime.now() - start).seconds < 120:    #120秒間の動画のため
    camera.annotate_text = dt.datetime.now().strftime('%Y.%m.%d %H:%M:%S')  #現在時刻を表示
    camera.wait_recording(0.4)    #0.4秒毎に時刻表示
dir_name = dt.datetime.now().strftime('%Y.%m.%d %H:%M:%S')
dir_path = '/home/pi/picamera/'+dir_name

camera.split_recording(dir_path+'movie.h264')  #動画を120秒毎に、別名で録画開始
camera.stop_recording()  #動画の録画停止
