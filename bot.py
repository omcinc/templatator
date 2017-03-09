import json
import os
import time
import traceback

from slackclient import SlackClient

from tttor.tttor import expand_all, draft_list, publish

# starterbot's ID as an environment variable
BOT_ID = os.environ.get("SLACK_BOT_ID")

# constants
AT_BOT = "<@" + BOT_ID + ">"
EXAMPLE_COMMAND = "do"

# instantiate Slack & Twilio clients
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))


def handle_command(command, channel):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    words = command.split(' ')
    verb = words[0]
    if verb == "help":
        post_help()
        return
    slugs = words[1:]
    if not slugs:
        post("Missing command arguments. Must be either 'all' or a list of slugs")
        return
    if slugs and slugs[0] == 'all':
        del slugs[0]
        if slugs:
            post("Wrong command arguments. Must be either 'all' or a list of slugs")
            return
    if verb == "check":
        expand_and_post(slugs, False)
    elif verb == "save":
        expand_and_post(slugs, True)
    elif verb == "drafts":
        drafts_and_post(slugs)
    elif verb == "publish":
        publish_and_post(slugs)
    else:
        post("I don't understand this command")


def post_help():
    post("check all|[slug...]: display templates that are not up to date")
    post("save all|[slug...]: update templates that are not up to date and save them as drafts")
    post("drafts all|[slug...]: list templates that are unpublished drafts")
    post("publish all|[slug...]: publish drafts")


def expand_and_post(slugs, save_drafts):
    if save_drafts:
        post("Expanding and saving drafts...")
    else:
        post("Expanding...")
    result = expand_all(slugs=slugs, save_drafts=save_drafts)
    post_not_found(result)
    expanded = result['expanded']
    if expanded:
        if save_drafts:
            post('Drafts saved: %s' % " ".join(expanded))
        else:
            post('Changes found in: %s' % " ".join(expanded))
    else:
        post('No changes found in templates')
    errors = result['errors']
    if errors:
        for error in errors:
            post(error)


def drafts_and_post(slugs=None):
    post("Checking drafts...")
    result = draft_list(slugs=slugs)
    post_not_found(result)
    drafts = result['drafts']
    if drafts:
        post('Drafts: %s' % " ".join(drafts))
    else:
        post('No drafts found')


def post_not_found(result):
    if 'not_found' in result and result['not_found']:
        post('Templates not found: %s' % " ".join(result['not_found']))


def publish_and_post(slugs):
    post("Publishing...")
    result = publish(slugs=slugs)
    post_not_found(result)
    published= result['published']
    if published:
        post('Published: %s' % " ".join(published))
    else:
        post("No drafts to publish")


def post(text):
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=text, as_user=True)


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                       output['channel']
    return None, None


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1  # 1 second delay between reading from firehose
    while True:
        try:
            if slack_client.rtm_connect():
                print("StarterBot connected and running!")
                while True:
                    command, channel = parse_slack_output(slack_client.rtm_read())
                    if command and channel:
                        handle_command(command, channel)
                    time.sleep(READ_WEBSOCKET_DELAY)
            else:
                print("Connection failed. Invalid Slack token or bot ID?")
        except:
                traceback.print_exc()
