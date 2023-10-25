import math
import socket

import cv2
import numpy as np
from cvzone.HandTrackingModule import HandDetector

UDP_IP_ADDRESS: str = "127.0.0.1"
UDP_PORT_NO: int = 22222
start: list[int] = [0, 0]
start_length: int = 0
count: int = 0
drag = False
incremented = False
decremented = False
switched_planet = False


def angle_between(p1, p2):
    ang1 = np.arctan2(*p1[::-1])
    ang2 = np.arctan2(*p2[::-1])
    return np.rad2deg((ang1 - ang2) % (2 * np.pi))


def reset_start():
    global start
    global count
    start = [0, 0]
    count = 0


def establish_connection():
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return client_sock


def send_command(client_sock, command):
    client_sock.sendto(bytes(command, 'utf-8'), (UDP_IP_ADDRESS, UDP_PORT_NO))


def watch_for_movement_controls(detected_hand, detector, dragged, client_sock):
    landmarks = detected_hand['lmList']
    global count
    global switched_planet
    if detector.fingersUp(detected_hand) == [1, 1, 1, 1, 1] and start[0] != 0 and start[1] != 0:
        new_x = 0
        new_y = 0
        movement_x = landmarks[9][0] - start[0]
        movement_y = landmarks[9][1] - start[1]
        if start[0] != 0 and start[1] != 0:
            new_x = 0.5 + movement_x
            new_y = 0.5 + movement_y

        # if new_x < 0.5:
        #     x = (new_x - 0.5) * -1
        # else:
        #     x = (0.5 - new_x)
        #

        if new_x > 0.5:
            x = new_x - 0.5
        else:
            x = (0.5 - new_x) * -1

        if new_y < 0.5:
            y = (new_y - 0.5)
        else:
            y = (0.5 - new_y) * -1

        x = round(x * 6, 2)
        y = round(y * 6, 2)
        coordinates = [x, y]
        posString = ','.join(map(str, coordinates))
        command = posString

        if dragged:
            send_command(client_sock, command + "," + "drag")

            if count > 1:
                start[0] = landmarks[9][0]
                start[1] = landmarks[9][1]
                count = 0
            else:
                count += 1
        elif not dragged:
            send_command(client_sock, command)

            if count > 2:
                reset_start()
            else:
                count += 1
    elif detector.fingersUp(detected_hand) == [0, 1, 1, 0, 0] and not switched_planet:
        print("next")
        switched_planet = True
        command = "Next"
        send_command(client_sock, command)
        command = ""
    elif detector.fingersUp(detected_hand) == [0, 1, 0, 0, 0] and not switched_planet:
        print("previous")
        switched_planet = True
        command = "Previous"
        send_command(client_sock, command)
        command = ""
    elif (detector.fingersUp(detected_hand) == [1, 0, 0, 0, 0] or detector.fingersUp(detected_hand) == [0, 0, 0, 0,
                                                                                                        0]) or dragged:
        start[0] = landmarks[9][0]
        start[1] = landmarks[9][1]
        switched_planet = False
        print("closed")
        command = ""
        # if (dragged):
        #     command = "stop"
        #     print("stop")

        send_command(client_sock, command)
    else:
        command = ""
        send_command(client_sock, command)


def watch_for_scale_controls(detected_hands, detector, img, client_sock):
    lmList1 = detected_hands[0]['lmList']
    lmList2 = detected_hands[1]['lmList']
    global start_length
    if start_length == 0:
        length, info, img = detector.findDistance(lmList1[8][:2], lmList2[8][:2], img)
        start_length = length

    length, info, img = detector.findDistance(lmList1[8][:2], lmList2[8][:2], img)
    angle = math.floor(angle_between(lmList1[8][:2], lmList2[8][:2]))
    scale = length - start_length
    command = str(math.floor(scale) * 2)
    send_command(client_sock, command)
    start_length = length


def main():
    cap = cv2.VideoCapture(0)
    client_sock = establish_connection()
    cap.set(3, 800)
    cap.set(4, 800)
    global start_length
    global drag

    detector = HandDetector(detectionCon=0.8)

    while True:
        success, img = cap.read()

        if not success:
            print("Ignoring empty camera frame.")
            continue

        hands, img = detector.findHands(img)
        img = cv2.flip(img, 1)
        if len(hands) == 1:
            if drag:
                reset_start();
                drag = False
            watch_for_movement_controls(hands[0], detector, drag, client_sock)
            start_length = 0
        elif len(hands) == 2:
            if detector.fingersUp(hands[0]) == [0, 0, 0, 0, 0] and detector.fingersUp(hands[1]) == [0, 0, 0, 0, 0]:
                command = 'stop '
                print(command)
                client_sock.sendto(bytes(command, 'utf-8'), (UDP_IP_ADDRESS, UDP_PORT_NO))
            elif detector.fingersUp(hands[0]) == [1, 1, 0, 0, 0] and detector.fingersUp(hands[1]) == [1, 1, 0, 0, 0]:
                watch_for_scale_controls(hands, detector, img, client_sock)
            elif detector.fingersUp(hands[0]) == [1, 1, 1, 1, 1] and (
                    detector.fingersUp(hands[1]) == [1, 0, 0, 0, 0] or detector.fingersUp(hands[1]) == [0, 0, 0, 0, 0]):
                drag = True
                watch_for_movement_controls(hands[0], detector, drag, client_sock)
            elif (detector.fingersUp(hands[0]) == [1, 0, 0, 0, 0] or detector.fingersUp(hands[0]) == [0, 0, 0, 0,
                                                                                                      0]) and detector.fingersUp(
                hands[1]) == [1, 1, 1, 1, 1]:
                drag = True
                watch_for_movement_controls(hands[1], detector, drag, client_sock)
            else:
                reset_start();
                start_length = 0
                command = ''
                client_sock.sendto(bytes(command, 'utf-8'), (UDP_IP_ADDRESS, UDP_PORT_NO))
        else:
            reset_start();
            start_length = 0
            command = ''
            client_sock.sendto(bytes(command, 'utf-8'), (UDP_IP_ADDRESS, UDP_PORT_NO))

        cv2.imshow('Hand Gesture Recognition', img)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break


if __name__ == '__main__':
    main()
