# Written by Prashant Mishra (GitHub: recreationdevelopers) for ISMIR 2022, and next set of events
# https://prashantmishra.xyz
# hi@prashantmishra.xyz
#
# Co-Author: Venkatakrishnan V K (GitHub: venkatKrishnan86)
# venkat86556@gmail.com

import slack_sdk
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from slack_sdk.errors import SlackApiError
import time

# [Workaround 1 Step 1]
# This step is to be used if you get a [SSL: CERTIFICATE_VERIFY_FAILED] error
import ssl
import certifi

ssl_context = ssl.create_default_context(cafile=certifi.where())

env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

# [Workaround 1 Step 2]
# Add ssl info to the WebClient if you get [SSL: CERTIFICATE_VERIFY_FAILED] error.
client = slack_sdk.WebClient(token=os.environ["SLACK_TOKEN"], ssl=ssl_context)


def retry(func, retries=100):
    """
    A decorator to retry a function call in case of SlackApiError.
    """

    def wrapper(*args, **kwargs):
        for _ in range(retries):
            try:
                return func(*args, **kwargs)
            except SlackApiError as e:
                if e.response["error"] == "ratelimited":
                    print("Rate limit exceeded. Retrying after 2 seconds...")
                    time.sleep(2)  # Wait before retrying
                else:
                    print(f"Slack API Error: {e.response['error']}.")
                    raise e  # Re-raise the exception if it's not a rate limit error
        print(f"Max retries exceeded for function '{func.__name__}'.")
        raise Exception(
            f"Max retries exceeded for function '{func.__name__}' in Slack API call."
        )

    return wrapper


# Sending Message to a particular channel as a Bot. The Bot MUST be added to the channel first.
# chat_postMessage requires the chat:write bot scope
def postMessageToASlackChannelAsBot(channelName, messageString):
    result = client.chat_postMessage(channel=channelName, text=messageString)
    print(result)


# Creating Channel as Bot. Requires the app to be first installed to the domain
# conversations_create requires the channels:manage bot scope and groups:write FOR PRIVATE channels
def createSlackChannelAsBot(channelName, boolChannelPrivacyON):

    # Call the conversations.create method using the WebClient
    result = retry(client.conversations_create)(
        # The name of the conversation
        name=channelName,
        is_private=boolChannelPrivacyON,
    )
    # Log the result which includes information like the ID of the conversation
    print(result)
    print("Channel Created!")


# Get all user data. Returns the data as a dictionary
# users_list requires bot scope 'users:read' and 'users:read.email' (Required for email)
def get_all_user_data():

    all_user_data = []

    result = retry(client.users_list)()

    users_array = result["members"]

    for user in users_array:
        # Key user info on their unique user ID
        user_id = user["id"]
        user_email = user["profile"].get(
            "email"
        )  # using .get() method to avoid error in the case of Bots, that don't have "email" value
        if user_email is not None:
            is_email_confirmed = user["is_email_confirmed"]
        else:
            is_email_confirmed = False

        # print (user_id)
        # print (user_email)
        # print ("Email confirmation: " + str(is_email_confirmed))
        # Store the entire user object (you may not need all of the info)

        all_user_data.append(
            {
                "user_id": user_id,
                "user_email": user_email,
                "Email_Confirmed": is_email_confirmed,
            }
        )

    # print(all_user_data)
    return all_user_data


# Loading all user data.
all_user_data = get_all_user_data()
user_email2id_map = {user["user_email"]: user["user_id"] for user in all_user_data}
user_id2email_map = {user["user_id"]: user["user_email"] for user in all_user_data}


# Get all channel data
# conversations_list required the channel:read bot scope
# limit sets the number of channels which we want to output, 1000 is the limit, default: 100
def get_all_channels_data():

    all_channel_data = []

    # conversations_list defaults to public_channel, so we add private_channels as well here
    channelDataType = "public_channel,private_channel"

    result = retry(client.conversations_list)(types=channelDataType, limit=1000)

    channels_array = result["channels"]

    # print(channels_array)

    for channel in channels_array:
        # Key conversation info on its unique ID
        channel_name = channel["name"]
        channel_id = channel["id"]

        # print (channel_id)

        all_channel_data.append(
            {"channel_name": channel_name, "channel_id": channel_id}
        )

    # print (all_channel_data)
    return all_channel_data


def loadAllChannelData():
    global channelsData
    channelsData = get_all_channels_data()


# Making channel data a global variable
channelsData = get_all_channels_data()
channel_name2id_map = {
    channel["channel_name"]: channel["channel_id"] for channel in channelsData
}
channel_id2name_map = {
    channel["channel_id"]: channel["channel_name"] for channel in channelsData
}


# Obtain Channel ID when given the channel name
def getChannelID(channelName):
    # data = get_all_channels_data(client)
    # for channel in channelsData:
    #     if channel["channel_name"] == channelName:
    #         return channel["channel_id"]
    # return None
    return channel_name2id_map.get(channelName, None)


# Obtain User ID given user email
def getUserID(user_email):
    # user_data = all_user_data
    # for user in user_data:
    #     if user["user_email"] == user_email:
    #         return user["user_id"]
    # return None
    return user_email2id_map.get(user_email, None)


# Obtain user email given user id
def getUserEmail(user_id):
    # user_data = all_user_data
    # for user in user_data:
    #     if user["user_id"] == user_id:
    #         return user["user_email"]
    # return None
    return user_id2email_map.get(user_id, None)


# Adding member to channel.
# conversations_invite requires bot scope channels:manage (and optionally user scope channels:write)
def addUserIDsToASlackChannelById(channelId, userIDs):
    """
    channelID: Channel ID
    userIDs: List of user IDs to be invited
    """

    return retry(client.conversations_invite)(channel=channelId, users=userIDs)


# Checks if the channel name already exists in the list of all public and private channels where the bot is added to
def isChannel(channelName):
    # channelsData = get_all_channels_data(client)
    # for channel_data in channelsData:
    #     if channel_data["channel_name"] == channelName:
    #         return True
    # return False
    return channelName in channel_name2id_map


# Creating all the private slack channels as given in the papers-full.csv file
# This function ONLY creates the channel with the bot added to it as of now
# Slack has a limit on creating new channels at one run time (=90)
def createPrivateSlackChannels(csvFile, channelColumnName):
    paper_data = pd.read_csv(csvFile)
    channels = paper_data[channelColumnName]
    # channelsData = get_all_channels_data(client)
    for channelName in channels:
        if not isChannel(channelName):
            createSlackChannelAsBot(channelName, True)


def createPublicSlackChannels(channels):
    # channelsData = get_all_channels_data(client)
    for channelName in channels:
        if not isChannel(channelName):
            createSlackChannelAsBot(channelName, False)


def createEmptyLinkColumnInCSVifNotPresent(csvFile, column_name, newCsvFile=None):
    """
    Parameters:
    -------------
    csvFile: The csv file to be read
    column_name: The name of the empty column
    newCsvFile (string): If None, the function will write a new column in csvFile, else will do so in a newCsvFile
    """
    paper_data = pd.read_csv(csvFile)
    for columns in paper_data:
        if columns == column_name:
            print("Column Already Exists")
            return
    paper_data[column_name] = ""
    if newCsvFile is None:
        paper_data.to_csv(csvFile, index=False)
    else:
        paper_data.to_csv(newCsvFile, index=False)


def addChannelLinksToCSV(csvFile, channelColumnName, newCsvFile=None):
    """
    Parameters:
    -------------
    csvFile: The csv file to be read
    channelColumnName: The name of the column containing channel names
    newCsvFile (string): If None, the function will overwrite in csvFile, else will write the csvFile with links in a newCsvFile
    """
    if newCsvFile is not None:
        createEmptyLinkColumnInCSVifNotPresent(csvFile, "channel_url", newCsvFile)
        paper_data = pd.read_csv(newCsvFile)
    else:
        createEmptyLinkColumnInCSVifNotPresent(csvFile, "channel_url")
        paper_data = pd.read_csv(csvFile)

    channels = paper_data[channelColumnName]
    # channelsData = get_all_channels_data(client)
    for i, channelName in enumerate(channels):
        if isChannel(channelName):
            paper_data.loc[i, "channel_url"] = (
                f"https://slack.com/app_redirect?channel={getChannelID(channelName)}"
            )
        else:
            print(
                f"Channel {channelName} does not exist in the workspace. Skipping link creation."
            )

    if newCsvFile is not None:
        paper_data.to_csv(newCsvFile, index=False)
    else:
        paper_data.to_csv(csvFile, index=False)


# For updating description of any channel
# Takes the channel name and the description which needs to be updated
# Requires admin.teams.write user scope and mainly Enterprise Version of Slack
def updateDescription(channelName, description):
    # channelsData = get_all_channels_data(client)
    if isChannel(channelName):
        channelID = getChannelID(channelName)
        assert channelID is not None, "Channel ID should not be None"
        client.admin_teams_settings_setDescription(
            token=client.token, description=description, team_id=channelID
        )
    else:
        print("Channel does not exist")


def updateTopicandPurpose(channelName, topic, purpose):
    """
    Updates the topic and purpose of a Slack channel.
    Requires channels:manage and groups:write bot scopes.
    """
    channel_id = getChannelID(channelName)
    assert channel_id is not None, "Channel ID should not be None"

    retry(client.conversations_setTopic)(channel=channel_id, topic=topic)
    retry(client.conversations_setPurpose)(channel=channel_id, purpose=purpose)


# Checks if user is already in the workspace
# users.read bot scope required
def isUserAlreadyInWorkspace(user_email):
    # user_data = all_user_data
    # for user in user_data:
    #     if user["user_email"] == user_email:
    #         return True
    # return False
    return user_email in user_email2id_map


# Returns the list of members' emails already in the channel 'channelName'
# channels.read and groups:read bot scope required
# Returns None for bots
def memberEmailsAlreadyInChannel(channelName):
    channel_id = getChannelID(channelName)
    assert channel_id is not None, "Channel ID should not be None"
    data = retry(client.conversations_members)(
        token=client.token,
        channel=channel_id,
    )
    # members = []
    # for user_id in data["members"]:
    #     members.append(getUserEmail(user_id))
    members = [getUserEmail(user_id) for user_id in data["members"]]
    return members


# Checks if a user already exists in a channel
def isUserAlreadyInChannel(user_email, channelName):
    members = memberEmailsAlreadyInChannel(channelName)
    # for member in members:
    #     if member == user_email:
    #         return True
    # return False
    return user_email in members


# Upto 1000 users can be invited
# channels:manage and groups:write bot scopes required
def inviteUserToChannel(user_email, channelName):
    if not isUserAlreadyInChannel(user_email, channelName):
        userID = getUserID(user_email)
        channelID = getChannelID(channelName)
        if userID is None:
            print(f"User {user_email} does not exist in the workspace.")
            return

        addUserIDsToASlackChannelById(channelID, userID)
        print("Invitation Sent")
    else:
        print(
            "Either member already exists in the channel or no such member exists in the workspace"
        )


# get_all_user_data(client)

# createSlackChannelAsBot(client, "private-channel-4", True)

# print(get_all_channels_data(client))

# print(isChannel('private-channel-4'))

# addUserIDsToASlackChannelById(client, "C046PV056V9", "U044YGS0H41")
# addUserIDsToASlackChannelById(client, "C046PV056V9", "U046Q1R7B18")

# print(len(get_all_channels_data(client)))
# print(isChannel('private-channel-two'))

# createPrivateSlackChannels(client, 'papers-full.csv', 'channel_name') # 89 channels created, 26 not created

# updateDescription(client, 'private-channel-two', 'Hello!')

# print(isChannel('hidden-from-bot-pvt'))

# print(isUserAlreadyInWorkspace(client, 'hi@prashantmishra.xyz'))

# print(memberEmailsAlreadyInChannel(client, 'private-channel-two'))

# print(isUserAlreadyInChannel(client, 'hi@prashantmishra.xyz', 'private-channel-two'))

# inviteUserToChannel(client, 'hi@prashantmishra.xyz', 'poster-1-01-shibata')

# addChannelLinksToCSV(client, 'papers-full.csv', 'channel_name')
"""
ToDo:
1) Invite users by email ID based on the CSV to the workspace (admin.users.invite API method)
    (a) Check if user was already invited before
    (b) Add user's Slack ID to the CSV in the respective row
2) Read CSV and create PRIVATE Slack channels (Some are not getting added as it shows name already taken, although not there. Maybe bot is not in those channels?)
    (a) Check if the channel already exists (DONE)
    (b) Add SCOPES to allow the bot to create Private Channels (DONE)
3) Add users to channels
    (a) Check if user already exists in the channel
4) Add bot to private channels where bot not present (Requires admin.users scopes)
"""

"""
TESTING


# get_all_channels_data(client)
# get_all_user_data(client)
# createSlackChannelAsBot(client, "channel-by-bot", False)

"""
