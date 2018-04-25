import time
import re
import threading
import datetime
import traceback
from termcolor import colored
from slackclient import SlackClient
try:
    import colored_traceback.auto
except ImportError:
    pass

def current_time():
    t = datetime.datetime.now()
    return colored(t.strftime("%Y-%m-%d %H:%M:%S"), 'green')

def parse_bot_commands(slack_events):
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            # Search for a direct mention at beginning of message
            matches = re.search("^<@(|[WU].+?)>(.*)", event["text"])
            mention_id = matches.group(1) if matches else None
            user_id = event["user"]
            name = bot.api_call("users.info", user=user_id)["user"]["real_name"]
            chan = bot.api_call("channels.info", channel=event["channel"])
            # If chan["ok"] is false, then channel is either deleted or an IM.
            if chan["ok"] == False and mention_id == bot_id:
                message = event["text"].split('<@U9RK6D3C3>')[1].strip()
                return name, message, event["channel"]
    return None, None, None

def handle_command(command, channel, user_name):
    global users
    global users_dict
    msg_parts = [x.strip() for x in command.split('|')]
    user_not_found = (
        "User not found. Did they join recently? "
        "Try reloading the users cache with `refresh users`."
    )
    if msg_parts[0] == 'send':
        # Usage: send | name | message
        user = msg_parts[1]
        message = msg_parts[2]

        if user.startswith('<@') and user.endswith('>'):
            user = user[2:-1]
            name = bot.api_call('users.info', user=user)['user']['real_name']
        elif user in users_dict:
            name = user
            user = users_dict[user]
        else:
            send_message(channel, user_not_found, user_name)
            return

        send_message(user, message, name)
        send_message(channel, f'Sending message to {name}', user_name)
    elif msg_parts[0] == 'send at':
        # Usage: send at | yyyy/mm/dd | hh:mm | user | message
        year, month, day = [int(x) for x in msg_parts[1].split("/")]
        hour, minute = [int(x) for x in msg_parts[2].split(":")]
        user = msg_parts[3]
        message = msg_parts[4]

        if user.startswith('<@') and user.endswith('>'):
            user = user[2:-1]
            name = bot.api_call('users.info', user=user)['user']['real_name']
        elif user in users_dict:
            name = user
            user = users_dict[user]
        else:
            send_message(channel, user_not_found, name)
            return
        now = datetime.datetime.today()
        run_at = now.replace(
            year = year,
            month = month,
            day = day,
            hour = hour,
            minute = minute,
            second = 0,
            microsecond = 0
        )
        delta_t = run_at - now.replace(microsecond = 0)
        secs = delta_t.seconds

        def func():
            send_message(user, message, name)
        threading.Timer(secs, func).start()
        hour, minute = [x for x in msg_parts[2].split(":")]
        send_message(channel, f'Sending message to {name} at {hour}:{minute}', user_name)
    elif msg_parts[0] == "repeat":
        # Usage: repeat | n | hh:mm | user | message
        repeat = msg_parts[1]
        hour, minute = [int(x) if x[0] != 0 else int(x[1]) for x in msg_parts[2].split(":")]
        user = msg_parts[3]
        message = msg_parts[4]
        if repeat != "forever":
            repeat = int(repeat)

        if user.startswith('<@') and user.endswith('>'):
            user = user[2:-1]
            name = bot.api_call('users.info', user=user)['user']['real_name']
        elif user in users_dict:
            name = user
            user = users_dict[user]
        else:
            send_message(channel, user_not_found, name)
            return

        timer_repeat(hour, minute, user, message, name, repeat)
        msg = repeat if repeat == 'forever' else f'{n} times'
        hour, minute = [x for x in msg_parts[2].split(":")]
        send_message(channel, f'Repeating message to {name} at {hour}:{minute} {msg}', user_name)
    elif msg_parts[0] == "refresh users":
        users = [user for user in bot.api_call("users.list")["members"]]
        users_dict = {user["real_name"]: user["id"] for user in users}
        send_message(channel, "Refreshed user list.", user_name)
    elif msg_parts[0] == "repeat on day":
        name = msg_parts[2]
        if name in users_dict:
            day = int(msg_parts[1])
            msg = msg_parts[2]
            user_awaiting.append(name)
            while name in user_awaiting:
                d = datetime.datetime.now
                next_day = next_weekday(d, day) # 0=Monday, 1=Tuesday, 2=Wednesday...

                run_at = next_day.replace(
                    hour = 17,
                    minute = 0,
                    second = 0,
                    microsecond = 0
                )
                delta_t = run_at - d.replace(microsecond = 0)
                secs = delta_t.seconds

                time.sleep(secs)
                send_message(users_dict[name], msg, name)
        else:
            send_message(channel, user_not_found, name)
    else:
        send_message(channel, "That's not a command.", user_name)

def send_message(channel, message, user):
    bot.api_call("chat.postMessage", channel = channel, text = message)

    chan = bot.api_call("channels.info", channel=channel)
    if chan["ok"] == True:
        channel_name = chan['channel']['name']
    else:
        channel_name = user
    print(f"{current_time()}  {colored(channel_name, 'cyan', attrs=['bold'])}: {message}")

def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
    return d + datetime.timedelta(days_ahead)

def timer_repeat(hour, minute, channel, message, user, repeat):
    now = datetime.datetime.today()
    run_at = (now + datetime.timedelta(days=1)).replace(
        hour = hour,
        minute = minute,
        second = 0,
        microsecond = 0
    )
    secs = (run_at - now.replace(microsecond=0)).seconds
    def func(hour, minute, channel, message, user, repeat):
        if repeat == 'forever':
            send_message(channel, message, user)
            time.sleep(1)
            timer_repeat(hour, minute, channel, message, user, repeat)
        else:
            repeat -= 1
            send_message(channel, message, user)
            if repeat:
                time.sleep(1)
                timer_repeat(hour, minute, channel, message, user, repeat)
    threading.Timer(secs, func, args=(hour, minute, channel, message, user, repeat)).start()

if __name__ == "__main__":
    with open("token.txt", "r", encoding="utf-8") as token_file:
        token = token_file.readline()[:-1]

    bot = SlackClient(token)
    bot_id = None
    if bot.rtm_connect(with_team_state=False):
        bot_id = bot.api_call("auth.test")["user_id"]
        # Get list of users in workspace
        users = [user for user in bot.api_call("users.list")["members"]]
        users_dict = {user['profile']['real_name']: user["id"] for user in users}
        user_awaiting = []
        print(current_time(), colored(' Bot Ready', 'grey', attrs=['bold']))

        # Main bot loop
        while True:
            user_name, command, channel = parse_bot_commands(bot.rtm_read())
            if command:
                print(f"{current_time()}  {colored(user_name, 'green', attrs=['bold'])}: {command}")
                try:
                    threading.Thread(
                        target=handle_command,
                        args=(command, channel, user_name)
                    ).start()
                except Exception as error:
                    traceback.print_exc()
            time.sleep(0.5)
    else:
        print("Connection failed.")
