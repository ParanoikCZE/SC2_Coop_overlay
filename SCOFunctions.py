import os
import json
import time
import requests
import threading
import traceback
import asyncio
import keyboard
import websockets
from ReplayAnalysis import analyse_replay
from MLogging import logclass

### Storage for all messages
OverlayMessages = []
lock = threading.Lock()
logger = logclass('SCOF','INFO')


def get_OverlayMessages():
    return OverlayMessages


def get_lock():
    return lock


def sendEvent(event):
    lock.acquire()
    OverlayMessages.append(event) 
    lock.release()


def check_replays(ACCOUNTDIR,PLAYER_NAMES,REPLAYTIME,AOM_NAME,AOM_SECRETKEY):
    """ Checks every 4s for new replays  """
    already_checked_replays = set()
    while True:   
        current_time = time.time()
        for root, directories, files in os.walk(ACCOUNTDIR):
            for file in files:
                file_path = os.path.join(root,file)
                if file.endswith('.SC2Replay') and not(file_path in already_checked_replays):
                    
                    already_checked_replays.add(file_path)

                    if current_time - os.path.getmtime(file_path) < REPLAYTIME: 
                        logger.debug(f'New replay: {file_path}')
                        try:   
                            replay_dict = analyse_replay(file_path,PLAYER_NAMES)
                            if len(replay_dict) > 0 :
                                logger.debug('Replay analysis result looks good, appending...')
                                sendEvent(replay_dict)
                                upload_to_aom(file_path,AOM_NAME,AOM_SECRETKEY,replay_dict)    
                                with open('SCO_analysis_log.txt', 'ab') as file: #save into a text file
                                    file.write((str(replay_dict)+'\n').encode('utf-8'))                              
                            else:
                                logger.error(f'ERROR: No output from replay analysis ({file})\n{traceback.format_exc()}') 
                            break
                        except Exception as e:
                            logger.error(f'{traceback.format_exc()}')

        time.sleep(3)   


def upload_to_aom(file_path,AOM_NAME,AOM_SECRETKEY,replay_dict):
    """ function handling uploading the replay on the Aommaster's server"""
    if AOM_NAME == None or AOM_SECRETKEY == None:
        return

    if (time.time() - os.path.getmtime(file_path)) > 60:
        return

    if replay_dict['mainCommander'] in [None,'']:
        sendEvent({'uploadEvent':True,'response':'Not valid replay for upload'})
        return

    url = f'http://starcraft2coop.com/scripts/assistant/replay.php?username={AOM_NAME}&secretkey={AOM_SECRETKEY}'
    try:
        with open(file_path, 'rb') as file:
            response = requests.post(url, files={'file': file})
        logger.info(f'Replay upload reponse: {response.text}')
     
        if 'Success' in response.text or 'Error' in response.text:
            sendEvent({'uploadEvent':True,'response':response.text})
    
    except Exception as e:
        sendEvent({'uploadEvent':True,'response':'Error'})
        logger.error(f'{traceback.format_exc()}')


async def manager(websocket, path):
    """ manages websocket connection for each client """
    overlayMessagesSent = 0
    logger.info(f"STARTING WEBSOCKET: {websocket}")
    while True:
        try:
            if len(OverlayMessages) > overlayMessagesSent:
                message = json.dumps(OverlayMessages[overlayMessagesSent])
                logger.info(f'Sending message #{overlayMessagesSent} through {websocket}')
                overlayMessagesSent += 1
                await websocket.send(message)
        except Exception as e:
            logger.error(f'{traceback.format_exc()}')
        finally:
            await asyncio.sleep(0.1)


def server_thread(PORT):
    """ creates a websocket server """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        start_server = websockets.serve(manager, 'localhost', PORT)
        logger.info('Starting websocket server')
        loop.run_until_complete(start_server)
        loop.run_forever()
    except Exception as e:
        logger.error(f'{traceback.format_exc()}')


def keyboard_thread_HIDE(HIDE):
    logger.info('Starting keyboard hide thread')
    while True:
        keyboard.wait(HIDE)
        logger.info('Hide event')
        sendEvent({'hideEvent': True})


def keyboard_thread_SHOW(SHOW):
    logger.info('Starting keyboard show thread')
    while True:
        keyboard.wait(SHOW)
        logger.info('Show event')
        sendEvent({'showEvent': True})