#!/usr/bin/env python3

import requests
import pdb
import sys

import subprocess
from bs4 import BeautifulSoup
from sys import exit
from time import time
from time import sleep
from re import sub as reSub
from re import compile as reCompile
from datetime import datetime
from json import loads, dumps
from sys import stdout
from os import system
from os import remove
from random import randint
from random import randrange
from argparse import ArgumentParser
from argparse import Action
from os.path import expanduser
from os.path import exists
from threading import Thread
from playsound import playsound
from typing import List
from bmsDecorator import debug
from bmsTypes import BMSRegion, City, BMSVenue, Venue, CinemaPageApiResponse
from collections import OrderedDict

def getObject():
    return type( '', (), {} ) # returns a simple object that can be used to add attributes

class NotificationThread( Thread ):
    def __init__( self, title, message, args ):
        Thread.__init__( self )
        self.title = title
        self.message = message
        self.args = args
        self.interval = 10 # will show desktop notification at this intervals ( seconds )

    def run( self ):
        if self.args.pushBullet:
            token = self.args.pushBullet[ 0 ]
            if len( self.args.pushBullet ) > 1:
                deviceList = self.args.pushBullet[ 1: ]
            else:
                # send to all devices
                deviceList = [ None ]
            configFilePath = expanduser( '~' ) + '/.ntfy.yml'
            for device in deviceList:
                with open( configFilePath, 'w+' ) as ntfyFile:
                    # set up config to push to given device
                    ntfyFile.write( 'backends: ["pushbullet"]\n' )
                    ntfyFile.write( 'pushbullet: {"access_token": "' + token + '"' )
                    if device is not None:
                        ntfyFile.write( ', "device_iden": "' + device + '"' )
                    ntfyFile.write( '}' )
                cmd = 'ntfy -t "{0}" send "{1}"'.format( self.title, self.message)
                system( cmd )
            if exists( configFilePath ):
                # we don't need this config anymore
                remove( configFilePath )
        while True:
            # Keep on sending desktop notifications till the program is closed
            start = time()
            cmd = 'ntfy -t "{0}" send "{1}"'.format( self.title, self.message)
            system( cmd )
            stop = time()
            timeRemaining = self.interval - ( stop - start )
            timeRemaining = int( round( timeRemaining if timeRemaining > 0 else 0 ) )
            sleep( timeRemaining )
        
class BMS( object ):

    def __init__( self, args ):
        self.args = args
        self.regionCode = self.args.regionCode.upper()
        self.date = self.args.date
        self.cinema = self.args.cinema
        self.movie = self.args.movie
        self.format = self.args.format
        self.alarm = self.args.alarm
        self.title = ''
        self.city: City = None
        self.cinema: Venue = None
        self.ss = requests.session()
        self.ss.headers.update(
            {
                # 'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                # 'Accept-Encoding': "gzip, deflate, br",
                # 'Accept-Encoding': "identity",
                # 'Host': "in.bookmyshow.com",
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36',
                # 'Connection': 'Keep-Alive'
            }
        )
        # self.ss.get( "https://in.bookmyshow.com/explore/movies-bengaluru" )
        # self.setRegionDetails( self.regionCode )

    def notification( self, title, message ):
        nThread = NotificationThread( title, message, self.args )
        nThread.start()
        # the thread will run till eternity or unless terminated using Ctrl-C

    def ringSineBell( self ):
        totalDuration = 0.0
        while totalDuration < 10.0:
            duration = 1.0 / randint(5,10)  # seconds
            freq = randrange( 200, 2000, 200 )  # Hz
            system('play --no-show-progress --null --channels 1 synth {} sine {}'.format(duration, freq))
            totalDuration += duration

    def ringBell( self ):
        totalDuration = 0.0
        while totalDuration < 8 * 60 * 60: # 8 hours
            duration = 1.0 / randint(5,10)  # seconds
            print( '\a', end="\r" )
            sleep( duration )
            totalDuration += duration

    def soundAlarm( self ):
        if self.alarm is not None:
            self.alarm = self.alarm.strip()
            if self.alarm.find( "~" ) == 0:
                # need to pass absolute path for home directory
                self.alarm = expanduser( '~' ) + self.alarm[ 1: ]
            while True:
                playsound( self.alarm )
        else:
            self.ringBell()

    def fetchVenues( self ) -> BMSVenue:
        '''
        Returns all available regions
        '''
        url = f"https://in.bookmyshow.com/pwa/api/de/venues?regionCode={self.city.RegionCode}&eventType=MT"
        cmd = [
            "curl",
            "--http1.1",
            "--user-agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            url
        ]
        data = subprocess.run( cmd, capture_output=True, text=True )
        return BMSVenue.parse_raw( data.stdout )

    def searchVenue( self, region: str ) -> List[Venue]:
        venues = self.fetchVenues()
        results = []
        
        for item in venues.BookMyShow.arrVenue:
            if (
                ( region.lower() in item.VenueCode.lower() ) or
                ( region.lower() in item.VenueName.lower() )
            ):
                results.append(item)
        
        return results
    
    def chooseVenue( self, venues: List[Venue] ) -> Venue:
        if len( venues ) == 0:
            print( "No venues found" )
            sys.exit( 1 )
        while True:
            for index, venue in enumerate( venues, start=1 ):
                print( f"{index}. {venue.VenueCode}: {venue.VenueName}" )
                
            choice = input("Enter the venue number of your choice (or 'q' to quit): ")
        
            if choice.lower() == 'q':
                sys.exit( 1 )
            
            try:
                choiceIdx = int( choice )
                if 1 <= choiceIdx <= len( venues ):
                    self.setVenue( venues[ choiceIdx - 1 ] )
                    return venues[ choiceIdx - 1 ]
                else:
                    print("Invalid choice. Please enter a valid number.")
            except ValueError:
                print("Invalid input. Please enter a number or 'q' to quit.")
                
    def setVenue( self, cinema: Venue ):
        self.cinema = cinema
        
    def fetchRegions( self ) -> BMSRegion:
        '''
        Returns all available regions
        '''
        url = "https://in.bookmyshow.com/api/explore/v1/discover/regions"
        cmd = [
            "curl",
            "--http1.1",
            "--user-agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            url
        ]
        data = subprocess.run( cmd, capture_output=True, text=True )
        return BMSRegion.parse_raw( data.stdout )

    def searchRegion( self, region: str ) -> List[City]:
        regions = self.fetchRegions()
        results = []
        
        def checkItem( cities: List[City] ):
            for item in cities:
                if (
                    ( region.lower() in item.RegionCode.lower() ) or
                    ( region.lower() in item.RegionName.lower() ) or
                    ( any( region.lower() in a.lower() for a in item.Alias ) )
                ):
                    results.append(item)
                    
        checkItem( regions.BookMyShow.TopCities )
        checkItem( regions.BookMyShow.OtherCities )
        
        return results
    
    def chooseRegion( self, regions: List[City] ) -> City:
        if len( regions ) == 0:
            print( "No regions found" )
            sys.exit( 1 )
        while True:
            for index, region in enumerate( regions, start=1 ):
                print( f"{index}. {region.RegionCode}: {region.RegionName}" )
                
            choice = input("Enter the regions number of your choice (or 'q' to quit): ")
        
            if choice.lower() == 'q':
                sys.exit( 1 )
            
            try:
                choiceIdx = int( choice )
                if 1 <= choiceIdx <= len( regions ):
                    self.setRegion( regions[ choiceIdx - 1 ])
                    return regions[ choiceIdx - 1 ]
                else:
                    print("Invalid choice. Please enter a valid number.")
            except ValueError:
                print("Invalid input. Please enter a number or 'q' to quit.")
    
    def setRegion( self, city: City ):
        self.city = city

    def getCinemaUrl( self ):

        curDate = datetime.now().strftime("%Y%m%d") if self.date is None else self.date
        venueName = reSub('[^0-9a-zA-Z ]+', '', self.cinema.VenueName ).lower().replace( " ", "-" )

        cinemaUrl = "https://in.bookmyshow.com/buytickets/"
        cinemaUrl += venueName
        cinemaUrl += "/cinema-"
        cinemaUrl += self.city.RegionCode.lower()
        cinemaUrl += "-"
        cinemaUrl += self.cinema.VenueCode
        cinemaUrl += "-MT/"
        cinemaUrl += curDate
        print( f"Cinema Url {cinemaUrl}" )
        return cinemaUrl
    
    def fetchCinemaPage( self ) -> BeautifulSoup:
        '''
        Returns all available regions
        '''
        url = self.getCinemaUrl()
        cmd = [
            "curl",
            "--http1.1",
            "--user-agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            url
        ]
        data = subprocess.run( cmd, capture_output=True, text=True )
        return BeautifulSoup( data.stdout, 'html5lib' )

    def checkCinemaAvailability( self ):
        '''
        Notifies if a show is available in your requested cinema
        '''
        cinemaSoup = self.fetchCinemaPage()
        # with open('cinema.html', 'w') as file:
        #     file.write(cinemaSoup.prettify())
        scripts = cinemaSoup.find_all( "script" )
        jsonMoviePattern = reCompile( r"var\s+UAPI\s+=\s+JSON.parse\(\"(.*)\"\);" )
        jsonMovieFormats: CinemaPageApiResponse = {}
        for script in scripts:
            jsonMovieFormats = jsonMoviePattern.search( str( script.string ) )
            if jsonMovieFormats:
                jsonMovieFormats = jsonMovieFormats.groups()[ 0 ]
                # now remove double slashes
                jsonMovieFormats = jsonMovieFormats.replace( "\\", "" )
                # now convert to json
                jsonMovieFormats = CinemaPageApiResponse.parse_raw( jsonMovieFormats )
                break
        
        # now see if your format is available
        found = False
        if jsonMovieFormats and len( jsonMovieFormats.ShowDetails ) > 0:
            for event in jsonMovieFormats.ShowDetails[ 0 ].Event:
                print( f"Matching {event.EventTitle}" )
                if self.movie.lower() in event.EventTitle.lower():
                    for eventFormat in event.ChildEvents:
                        if self.format is None:
                            # movie is available in any format
                            found = True
                            break
                        elif eventFormat.EventDimension == self.format:
                            # we found our format
                            found = True
                            break

        # string to print format if available
        formatAvailable = ""
        if self.format is not None:
            formatAvailable = " in " + self.format

        if found:
            # Movie tickets are now available
            print( "HURRAY! Movie tickets are now available" + formatAvailable )
            self.notification( "Hurray!", "Tickets for " + self.movie + " at " + self.title + " are now available" + formatAvailable )
            self.soundAlarm()
            return True
        elif len( jsonMovieFormats.ShowDetails ) > 0 and jsonMovieFormats.ShowDetails[ 0 ].Event:
            # The requires format isn't available or the movie is yet to be released
            availableFormats = [ eventFormat.EventDimension for eventFormat in event.ChildEvents for event in jsonMovieFormats.ShowDetails[ 0 ].Event if self.movie.lower() in event.EventTitle.lower() ]
            if availableFormats:
                print( "The available format(s) : " + ( ", ".join( availableFormats ) ) )
                print( "Movie is not available in requested " + self.format + " format, will retry..." )
                return False
            else:
                print( "Movie tickets aren't available yet, retrying..." )
                return False
        else:
            print( "Movie tickets aren't available yet, retrying..." )
            return False

def parser():
    parser = ArgumentParser( prog=sys.argv[ 0 ],
                             description="A script to check if tickets are available for the movie in the specified cinema at a given date",
                             epilog="And you will be the first one to be notified as soon as the show is available" )
    parser.add_argument( '-m', '--movie', required=True, action='store', type=str, help="The movie you're looking to book tickets for" )
    parser.add_argument( '-c', '--cinema', required=True, action='store', type=str, help="The cinema in which you want to watch the movie" )
    parser.add_argument( '-f', '--format', action='store', choices=[ "2D", "3D", "IMAX 2D", "IMAX 3D" ], type=str, help="Preferred format, if any" )
    parser.add_argument( '-d', '--date', required=True, action='store', type=str, help="Format: YYYYMMDD | The date on which you want to book tickets." )
    parser.add_argument( '-r', '--regionCode', required=True, action='store', type=str, help="The region code of your area; BANG for Bengaluru" )
    parser.add_argument( '-i', '--interval', action='store', type=int, help="BMS server will be queried every interval seconds", default=60 )
    parser.add_argument( '-a', '--alarm', action='store', type=str, help="Path to audio file that will play as an alarm when notified ( optional )" )
    parser.add_argument( '-b', '--pushBullet', action='store', metavar=( "ACCESS_TOKEN", "DEVICE_ID" ), type=str, nargs='+', help="Send notification to your device using pushbullet" )
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parser()
    interval = args.interval
    status = False
    bms = BMS( args )
    regions = bms.searchRegion( args.regionCode )
    bms.chooseRegion( regions )
    venues = bms.searchVenue( args.cinema )
    bms.chooseVenue( venues )
    print( f'Selected {bms.cinema.VenueName} in region {bms.city.RegionName}' )
    while not status:
        start = time()
        retry = 0
        while retry < 60:
            # only retry for some time on connectivity issues
            try:
                status = bms.checkCinemaAvailability()
                break
            except AssertionError:
                print( "Seems like we lost the connection mid-way, will retry..." )
                retry += 1
            except KeyboardInterrupt:
                sys.exit( 1 )
            except Exception as e:
                print( "Something unexpected happened; Recommended to re-run this script with correct values" )
                print( "Printing traceback:" )
                print( e )
                break
        if not status:
            try:
                stop = time()
                timeRemaining = interval - ( stop - start )
                timeRemaining = int( round( timeRemaining if timeRemaining > 0 else 0 ) )
                sleep( timeRemaining )
            except KeyboardInterrupt:
                sys.exit( 1 )
            except Exception as e:
                print( "Something unexpected happened; Recommended to re-run this script with correct values" )
                break
