#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec 13 18:57:11 2022

@author: Alessandro
"""

import json
import datetime

class Catalog:
    def __init__(self, filename):
        self.filename = filename
        try:
            self.catalog = json.load(open(self.filename))
        except:
            print("Catalog does not exist, building a default structure...")
            self.catalog = {"Breeds":[],
                            "Devices":[],
                            "Dogs":[]}
            
        self.defaultBreed = {"BreedID": 0,
                             "Name": "",
                             "ActivityTime": 0,
                             "MaxHeartRate": 0,
                             "MinHeartRate": 0,
                             "MaxAmbientTemperature": 0,
                             "MinAmbientTemperature": 0,
                             "MaxAmbientHumidity": 0,
                             "MinAmbientHumidity": 0}
        
        x = datetime.datetime.now()
        self.defaultDog = {"DogID": 0,
                           "Name": "",
                           "Breed": "",
                           "Age": 0,
                           "Sex": 0, # 0 for male, 1 for female
                           "DailyActivity": 0,
                           "Escape": False,
                           "LastAntiTickApplication": x.strftime("%d/%m/%Y")} 
        
        self.defaultDevice = {"DeviceID": 0,
                              "Name": "",
                              "Available": True,
                              "MeasureType": "",
                              "MeasureUnit": "",
                              "CommunicationParadigm": []}
    
    def addBreed(self):
        for key in self.defaultBreed:
            print("The feature to be added is:", key)
            if type(self.defaultBreed[key]) == int:
                valid = False
                while not valid:
                    try: 
                        self.defaultBreed[key] = int(input("Enter an integer value: "))
                        valid = True
                    except:
                        print("Invalid input. Please, type an integer.")
            else:
                self.defaultBreed[key] = input("Enter an input: ")
        self.catalog["Breeds"].append(self.defaultBreed.copy())
        
    def addDevice(self):
        for key in self.defaultDevice:
            print("The feature to be added is:", key)
            if type(self.defaultDevice[key]) == int:
                valid = False
                while not valid:
                    try: 
                        self.defaultDevice[key] = int(input("Enter an integer value: "))
                        valid = True
                    except:
                        print("Invalid input. Please, type an integer.")
            elif type(self.defaultDevice[key]) == list:
                valid = False
                while not valid:
                    try:
                        val = int(input("How many items you want in the list?: "))
                        valid = True
                    except:
                        print("Invalid input. Please, type an integer.")
                for i in range(val):
                    self.defaultDevice[key].append(input("Enter an input: "))
            else:
                self.defaultDevice[key] = input("Enter an input: ")
        self.catalog["Devices"].append(self.defaultDevice.copy())
            
    def addDog(self):
        for key in self.defaultDog:
            if key != "DailyActivity":
                print("The feature to be added is:", key)
                if type(self.defaultDog[key]) == int:
                    if key == "Sex":
                        print("0 for male, 1 for female")
                    valid = False
                    while not valid:
                        try: 
                            self.defaultDog[key] = int(input("Enter an integer value: "))
                            valid = True
                        except:
                            print("Invalid input. Please, type an integer.")
                else:
                    if key == "LastAntiTickApplication":
                        print("In this case, use a date in format dd/mm/yyyy")
                    self.defaultDog[key] = input("Enter an input: ")
        self.catalog["Dogs"].append(self.defaultDog.copy())
                    
    def run(self):
        print("Welcome to the catalog builder")
        again = True
        while again:
            print(f"The categories to add are {len(self.catalog.keys())}")
            for key in self.catalog:
                print("-",key)
            valid = False
            while not valid:
                category = input("Enter a category to build or type \"stop\" to exit: ")
                if (category.capitalize() in list(self.catalog.keys())) or (category.capitalize() == "Stop"):
                    valid = True
                else:
                    print("Invalid input. Please, type one of the characteristics above")
            if category.capitalize() == "Stop":
                again = False
                print("Bye bye")
            else:
                if category.capitalize() == list(self.catalog.keys())[0]:
                    self.addBreed()
                elif category.capitalize() == list(self.catalog.keys())[1]:
                    self.addDevice()
                elif category.capitalize() == list(self.catalog.keys())[2]:
                    self.addDog()
                valid = False
                while not valid:
                    confirm = input("Whould you like to insert another item? ")
                    if confirm.lower() == "yes":
                        valid = True
                    elif confirm.lower() == "no":
                        again = False
                        valid = True
                    else: 
                        print("Wrong input, type \"yes\" or \"no\"")
                        
        fp = open(self.filename, "w")
        json.dump(self.catalog, fp, indent = 2)
        fp.close()
            
        
if __name__ == "__main__":
    IoPeT = Catalog("catalog.json")
    IoPeT.run()