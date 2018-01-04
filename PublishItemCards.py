import time
from arcgis.gis import GIS

import os, re, json, traceback
import urllib.request as urlopen
import urllib.request as request
from datetime import datetime

online_username = ""
online_password = ""
online_connection = ""
gis_online_connection = GIS(online_connection, online_username, online_password)

def getMetadata(metadata_key,value):
    try:
        url = "https://nameless-retreat-53455.herokuapp.com/goals?ids=" + value
        print(url)
        req = request.Request(url)
        response = urlopen.urlopen(req)
        response_bytes = response.read()
        json_data = json.loads(response_bytes.decode('UTF-8'))
        if "icon_url" not in json_data["data"][0]:
            json_data["data"][0]["icon_url"] = "https://raw.githubusercontent.com/UNStats-SDGs/sdgs-data/master/images/en/TGG_Icon_Color_"+ value + ".png"
        return json_data["data"][0]
    except:
        return "https://raw.githubusercontent.com/UNStats-SDGs/sdgs-data/master/images/en/TGG_Icon_Color_"+ value + ".png"

def addItemtoOnline(item_properties, thumbnail):
    # Check if there is a group here
    query_string = "title:'{}' AND owner:{}".format(item_properties["title"], online_username)
    search_results = gis_online_connection.content.search(query_string)
    if not search_results:
        return gis_online_connection.content.add(item_properties=item_properties, thumbnail=thumbnail)
    else:
        for search_result in search_results:
            if search_result["title"] == item_properties["title"]:
                search_result.update(item_properties=item_properties, thumbnail=thumbnail)
                return search_result
    return None

def createGroup(group_info):
    try:
        # Add the Service Definition to the Enterprise site
        item_properties = dict({
            'title': group_info["title"],
            'snippet': group_info["snippet"],
            'description': group_info["description"],
            'tags': ', '.join([group_info["title"], 'Open Data', 'Hub']),
            'thumbnail': group_info["thumbnail"],
            "isOpenData": True,
            "access": "public",
            "isInvitationOnly": True,
            "protected": True
        })

        # Check if there is a group here
        query_string = "title:'{}' AND owner:{}".format(group_info["title"], online_username)
        search_results = gis_online_connection.groups.search(query_string)
        group = None
        if not search_results:
            return gis_online_connection.groups.create_from_dict(item_properties)
        else:
            group_found = False
            for search_result in search_results:
                if search_result["title"] == group_info["title"]:
                    group_found = True
                    search_result.update(title=group_info["title"], tags=group_info["tags"], description=group_info["description"],
                                         snippet=group_info["snippet"], access="Public", thumbnail=group_info["thumbnail"])
                    return search_result
            # The correct group was not found in the search results add it now
            if not group_found:
                return gis_online_connection.groups.create_from_dict(item_properties)
    except:
        traceback.print_exc()

def processSDGInfomation(indicator_code=None, series_code=None):
    try:
        #  Get the JSON Values from the SDG API
        url = "https://unstats.un.org/SDGAPI/v1/sdg/Goal/List?includechildren=true"
        req = request.Request(url)
        response = urlopen.urlopen(req)
        response_bytes = response.read()
        json_data = json.loads(response_bytes.decode('UTF-8'))

        for goal in json_data:
            # Get the Thumbnail from the SDG API
            goal_metadata = getMetadata("goals", goal["code"])
            print(goal_metadata)
            if "icon_url" in goal_metadata:
                thumbnail = goal_metadata["icon_url"]
            else:
                thumbnail = "http://undesa.maps.arcgis.com/sharing/rest/content/items/aaa0678dba0a466e8efef6b9f11775fe/data"

            # Create a Group for the Goal
            group_goal_properties = dict()
            group_goal_properties["title"] = "Goal " + goal["code"]
            group_goal_properties["snippet"] = goal["title"]
            group_goal_properties["description"] = goal["description"]
            group_goal_properties["tags"] = [group_goal_properties["title"]]
            if "keywords" in goal_metadata:
                if "tags" in goal_metadata["keywords"]:
                    group_goal_properties["tags"] += goal_metadata["keywords"]["tags"]
                if "descriptions" in goal_metadata["keywords"]:
                    group_goal_properties["tags"] += goal_metadata["keywords"]["descriptions"]
                if "groups" in goal_metadata["keywords"]:
                    group_goal_properties["tags"] += goal_metadata["keywords"]["groups"]
            group_goal_properties["thumbnail"] = thumbnail
            group_id = createGroup(group_goal_properties)

            processed_tags = False
            for target in goal["targets"]:
                group_target_properties = dict()
                group_target_properties["tags"] = ["Target " + target["code"], target["code"]]
                group_id.update(tags=group_id["tags"] + group_target_properties["tags"])

                # Iterate through each of the targets
                # Allow processing a single indicator
                # code
                for indicator in target["indicators"]:
                    if indicator_code and not indicator["code"] == indicator_code:
                        continue

                    process_indicator = dict()
                    process_indicator["name"] = "Indicator " + indicator["code"]  # eg. Indicator 1.1.1
                    process_indicator["tags"] = [indicator["code"], process_indicator["name"]]
                    # Append the keyword tags from the metadata as well
                    group_id.update(tags=group_id["tags"] + process_indicator["tags"])

                    process_indicator["snippet"] = indicator["code"] + ": " + indicator["description"]
                    process_indicator["description"] = "<p><b>Goal: </b>" + goal['description'] + "</p><p><b>Target: </b>" + target['description'] + "</p><p><b>Indicator: </b>" + indicator["description"] + "</p>"
                    process_indicator["credits"] = "UNSD"
                    process_indicator["thumbnail"] = thumbnail

                    for series in indicator["series"]:
                        # Determine if we are processing this query Only process a specific series code
                        if indicator_code and not (series["code"] == series_code or series_code is None):
                            continue

                        # indicator_code = None
                        item_properties = dict()
                        item_properties["title"] = process_indicator["name"] + " (" + series["code"] +")"
                        if not series["description"]:
                            series["description"] = series["code"]
                        snippet = series["code"] + ": " + series["description"]
                        item_properties["snippet"] = (snippet[:250] + '..') if len(snippet) > 250 else snippet
                        item_properties["description"] = process_indicator["description"] + "<p><b>Series Information: </b>(" + series["code"] + ") " + series["description"] + "</p>"
                        item_properties["tags"] = group_goal_properties["tags"] + group_target_properties["tags"] + process_indicator["tags"] + [series["code"]]
                        item_properties["type"] = "Feature Service"
                        item_properties["url"] = "http://floating-dawn-26036.herokuapp.com/sdgs/series/" + series["code"] + "/FeatureServer"

                        # Add this item to ArcGIS Online
                        print ('Processing series code:', indicator["code"], series["code"])
                        try:
                            online_item = addItemtoOnline(item_properties=item_properties, thumbnail=thumbnail)
                            # Share this content with the goals group
                            online_item.share(everyone=True, org=True, groups=group_id["id"], allow_members_to_edit=False)
                            # Update the Group Information with Data from the Indicator and targets
                            group_id.update(tags=group_id["tags"] + [series["code"]])
                        except:
                            print('Failed to process series code:', indicator["code"], series["code"], item_properties)

        return
    except:
        traceback.print_exc()

if __name__ == "__main__":
    start_time = str(datetime.now())
    processSDGInfomation()
    end_time = str(datetime.now())
    print(start_time, end_time)
    print('Completed')
