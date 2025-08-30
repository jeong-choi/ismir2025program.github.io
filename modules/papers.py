import pandas as pd
import copy
import time
import re
import os
from typing import Optional
from tqdm import tqdm

from utils import slack as slackUtils


def title2channelID(
    title: str,
    paper_id: Optional[None] = None,
    session_number: Optional[int] = None,
    paper_number: Optional[int] = None,
) -> str:
    if session_number is not None and paper_number is not None:
        prefix = f"p{session_number}-{paper_number}"
    else:
        prefix = f"p{paper_id}"

    # Clean and normalize the title
    cleaned_title = title.lstrip().lower()
    cleaned_title = re.sub(r"[+?._:,]", "", cleaned_title)  # Remove unwanted characters
    cleaned_title = re.sub(r"[&]", "and", cleaned_title)  # Replace '&' with 'and'
    cleaned_title = re.sub(
        r"[\s,_]", "-", cleaned_title
    )  # Replace spaces and underscores with '-'

    # Split the cleaned title into parts and join the first three with '-'
    title_parts = cleaned_title.split("-")[:3]
    formatted_title = "-".join(title_parts)

    return f"{prefix}-{formatted_title}"


# Defining the class that exposes the methods related to papaers.
class Papers:
    """
    This method takes the config data loaded and the papers csv file.
    """

    def __init__(self, papersCsvFile, useDummyValues):
        self.papersCsvFile = papersCsvFile
        self.useDummyValues = useDummyValues

    """
    This method inputs the zoomUtils and setup zoom calls for the all the sessions.
    """

    def setupSlackChannels(self, *_):
        if self.papersCsvFile is None:
            raise Exception("self.papersCsvFile passed in contructor is null")

        # Reading the papers data.
        csv_data = pd.read_csv(self.papersCsvFile)

        slack_channel_column = "slack_channel"

        csv_data.loc[:, slack_channel_column] = ""

        # Iterating over each row and creating the slack_channel_column
        # Format is P<session_nunmber>-<position>-<author_last_name>.
        # print(csv_data["primary_author"])
        for index, row in csv_data.iterrows():
            session_number = row["session"]
            position = row["position"]
            csv_data.loc[index, slack_channel_column] = title2channelID(
                row["title"],
                session_number=session_number,
                paper_number=position,
            )
            # names_array = row["primary_author"].lower().strip().split()
            # names_array.reverse()
            # csv_data.loc[index, slack_channel_column] = (
            #     "p"
            #     + str(row["session"])
            #     + "-"
            #     + "{:0>2}".format(row["position"] + 1)
            #     + "-"
            #     + names_array[0]
            # )

        print("Data after adding the slack column channel: ", csv_data)
        # Updating the file with the details to be able to write the slack columns.
        csv_data.to_csv(self.papersCsvFile, index=False)

    def createSlackChannels(self, *_):
        if self.papersCsvFile is None:
            raise Exception("self.papersCsvFile passed in contructor is null")

        # Reading the papers data.
        csv_data = pd.read_csv(self.papersCsvFile)
        slack_channel_column = "slack_channel"
        channel_names = csv_data[slack_channel_column].tolist()

        print("########### Now creating slack channels ##########")
        slackUtils.createPublicSlackChannels(channel_names)

        #  force reloading all channel data.
        slackUtils.loadAllChannelData()

        # Adding the channel link to the file.
        slackUtils.addChannelLinksToCSV(self.papersCsvFile, slack_channel_column)

    def inviteAuthorsToChannels(self):
        if self.papersCsvFile is None:
            raise Exception("self.papersCsvFile passed in contructor is null")
        # Reading the papers data.
        csv_data = pd.read_csv(self.papersCsvFile)
        slack_channel_column = "slack_channel"
        # Adding the authors to the papers channel.
        user_details = {}
        for index, data in csv_data.iterrows():
            # print("Row is: ", data)
            user_details[data[slack_channel_column]] = (
                str(data["author_emails"]).replace(" ", "").replace("*", "").split(";")
            )

        if self.useDummyValues:
            print("Have to use dummy values!!!")
            for key, value in user_details.items():
                user_details[key] = [
                    # "swapnilgupta.iiith@gmail.com",
                    # "sharathadavanne@gmail.com",
                    os.environ.get("DUMMY_EMAIL", "default_dummy_email@example.com")
                ]

        # Sending invites to users.
        print("The user details are: ", user_details)

        # Finally sending invites.
        for key, emails in user_details.items():
            for email in emails:
                print("Sending email for ", key, " to ", email)
                slackUtils.inviteUserToChannel(email, key)

    def setSlackChannelDescription(self):
        if self.papersCsvFile is None:
            raise Exception("self.papersCsvFile passed in contructor is null")

        # Reading the papers data.
        csv_data = pd.read_csv(self.papersCsvFile)

        with tqdm(csv_data.iterrows()) as pbar:
            pbar.set_description("Setting Slack channel descriptions")
            for index, row in pbar:
                channel_name = row["slack_channel"]
                title = row["title"]
                paper_id = row["uid"]
                authors = (
                    row["authors_and_affil"]
                    .replace("*", "")
                    .replace(";", ",")
                    .replace("  ", " ")
                )
                authors = (
                    re.sub(r"\s*\(.*?\)", "", authors).replace("(", "").replace(")", "")
                )
                topic = f"Paper {paper_id}: {title}"
                purpose = f"\n{title}\nhttps://ismir2025program.ismir.net/poster_{paper_id}.html\n{authors}"[
                    :250
                ]

                slackUtils.updateTopicandPurpose(channel_name, topic, purpose)
                pbar.set_postfix(channel=channel_name)
