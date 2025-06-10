version_number = "1.0"

import subprocess
import csv
import re
import io
import os
import time
import sys
import threading
import shutil
import json
from datetime import datetime, timedelta, date
from concurrent.futures import ThreadPoolExecutor, as_completed

# Enable ANSI Support and Disable PowerShell Window for Windows 10+
if os.name == "nt":
    os.system("")
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0

# Open config file.
with open("ADC_Config.json", "r") as f:
    config = json.load(f)

spinner_done = threading.Event()





'''
################################################
Take user input to activate different functions.
################################################

5/29/2025
'''
def main():

    verify_ad_tools()
    dry_run = config["All"].get("dry_run_default", "true").lower() == "true"
   
    
    while True:
        intro(main_color, RESET, version_number)
        display_dry_run(dry_run)

        # Get user input
        clean_choice = main_option_list()

        
        try:
            clean_choice = int(clean_choice)
            
            # If they are cleaning ask if they want to disable or delete.
            try:
                if (clean_choice == 2) or (clean_choice == 3):
                    disde_choice = sub_option_list()
                    disde_choice = int(disde_choice)
                else:
                    disde_choice = 0
                    
                if disde_choice == 1:
                    intent = "disable"
                elif disde_choice == 2:
                    intent = "delete"
            except ValueError:
                print("Invalid Option: Please enter a number.")
                time.sleep(2)
                continue
                
            # Disable/Enable dry run.
            if clean_choice == 1:
                dry_run = not dry_run
            
            elif clean_choice == 2:
                user_cleaner(intent=intent, dry_run=dry_run)
            elif clean_choice == 3:
                computer_cleaner(intent=intent, dry_run=dry_run)

            # Joke    
            elif clean_choice == 4:
                print("Then why are you here?\n")
                time.sleep(3)
                continue
            elif clean_choice == 5:
                ad_stats()
            

                
            # Exit program
            elif clean_choice == 0:
                break
            
            else:
                print("Invalid Option: Please try again.\n")
        except ValueError:
            print("Invalid Option: Please enter a number.")
            time.sleep(2)
            






'''
##################################################################
Takes variables from other functions to disable unwanted accounts.
##################################################################

5/30/2025
'''
def clean_ad_objects(
    ps_command: str,
    object_type: str,
    intent: str,
    inactivity_years: int,
    get_identifier: callable,
    bypass_condition: callable,
    command_template: str,
    filename_prefix: str,
    dry_run: bool
):
    
    global spinner_done
    separator(main_color, RESET)
    
    print(f"This will {main_color}{intent.upper()}{RESET} all {main_color}{object_type.upper()}S{RESET} in Active Directory that have been inactive for {main_color}{inactivity_years}{RESET} years.")

    
    get_consent(dry_run)

    spinner_done.clear()
    spinner_thread = threading.Thread(target=spinner_task)
    spinner_thread.start()

    process = run_powershell_command(ps_command)
    if process.returncode != 0:
        spinner_done.set()
        spinner_thread.join()
        print(f"\n\n{RED}PowerShell Error: {RESET}", process.stderr)
        print(f"{RED}Failed command: {RESET}", ps_command)
        return



    baseline = date.today() - timedelta(days=365 * inactivity_years)
    reader = csv.DictReader(io.StringIO(process.stdout))

    bypassed = []
    affected = []

    for row in reader:
        try:
            creation_date = datetime.strptime(row["whenCreated"].split()[0], "%m/%d/%Y").date()

            if intent == "delete":
                when_changed = datetime.strptime(row["whenChanged"].split()[0], "%m/%d/%Y").date() if row["whenChanged"].strip() else creation_date
                activity_date = when_changed
                if object_type == "user":
                    info = {
                        "SamAccountName": row["SamAccountName"],
                        "whenCreated": creation_date,
                        "whenChanged": when_changed
                    }
                elif object_type == "computer":
                    info = {
                        "Name": row["Name"],
                        "IPv4Address": row["IPv4Address"],
                        "whenCreated": creation_date,
                        "whenChanged": when_changed
                    }
                     
            elif intent == "disable":
                last_logon = datetime.strptime(row["LastLogonDate"].split()[0], "%m/%d/%Y").date() if row["LastLogonDate"].strip() else creation_date
                activity_date = last_logon
                if object_type == "user":
                    info = {
                        "SamAccountName": row["SamAccountName"],
                        "whenCreated": creation_date,
                        "LastLogonDate": last_logon
                    }
                elif object_type == "computer":
                    info = {
                        "Name": row["Name"],
                        "IPv4Address": row["IPv4Address"],
                        "whenCreated": creation_date,
                        "LastLogonDate": last_logon
                    }                
            
        except Exception as e:
            print(f"Error parsing dates for row {row}: {e}")
            continue
        

        if activity_date <= baseline:
            if bypass_condition(row):
                bypassed.append(info)
            else:
                affected.append(info)

    spinner_done.set()
    spinner_thread.join()

    print(f"{main_color}{len(affected)} {object_type.upper()}S{RESET} are about to be {main_color}{intent.upper()}D{RESET}.")

    get_consent(dry_run)

    spinner_done.clear()
    spinner_thread = threading.Thread(target=spinner_task)
    spinner_thread.start()

    if not dry_run:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for obj in affected:
                ps_cmd = disable_command_template.format(get_identifier(obj))
                futures.append(executor.submit(run_powershell_command, ps_cmd))

            for future in as_completed(futures):
                success = future.result()

    else:
        print(f"\r{main_color}NO CHANGES MADE{RESET}\n")


    spinner_done.set()
    spinner_thread.join()

    print_results(filename_prefix, intent, object_type, bypassed, affected)

    separator(main_color, RESET)





'''
########################
Disable old AD accounts.
########################

5/30/2025
'''  
def user_cleaner(intent=None, dry_run=None):
    
    if intent == "delete":
        user_ps = '''
        Get-ADUser -Filter "Enabled -ne 'True'" -Properties Surname, GivenName, whenCreated, whenChanged, MemberOf, DistinguishedName |
        Select-Object SamAccountName, Surname, GivenName, whenCreated, whenChanged, DistinguishedName,
        @{Name="MemberOf";Expression={($_.MemberOf -join ";")}} |
        ConvertTo-Csv -NoTypeInformation
        '''
        command_template = 'Remove-ADAccount -Identity "{}" -Confirm:$false'
        inactivity_years=int(config["User"].get("user_disabled_years", 1))
        
    elif intent == "disable":
        user_ps = '''
        Get-ADUser -Filter "Enabled -eq 'True'" -Properties Surname, GivenName, whenCreated, LastLogonDate, MemberOf, DistinguishedName |
        Select-Object SamAccountName, Surname, GivenName, whenCreated, LastLogonDate, DistinguishedName,
        @{Name="MemberOf";Expression={($_.MemberOf -join ";")}} |
        ConvertTo-Csv -NoTypeInformation
        '''
        inactivity_years=int(config["User"].get("user_years_since_logon", 5))
        command_template = 'Disable-ADAccount -Identity "{}"'


    name_exclusion = config["User"]["exclude_name_starting_with"]
    def bypass_condition(r):
        sam_name = r.get("SamAccountName", "").strip()
        group_match = re.search(config["User"].get("user_bypass_group", ""), r.get("MemberOf", ""))
        name_match = name_exclusion and sam_name.startswith(name_exclusion)
        return group_match or name_match

    clean_ad_objects(
        ps_command=user_ps,
        object_type="user",
        intent=intent,
        inactivity_years=inactivity_years,
        get_identifier=lambda r: r["DistinguishedName"],
        bypass_condition=bypass_condition,
        command_template=command_template,
        filename_prefix="user",
        dry_run=dry_run
    )





'''
#########################
Disable old AD computers.
#########################

5/28/2025
'''  
def computer_cleaner(intent, dry_run):
    if intent == "delete":
        computer_ps = '''
        Get-ADComputer -Filter "Enabled -ne 'True'" -Properties IPv4Address, whenCreated, whenChanged, MemberOf, DistinguishedName |
        Select-Object Name, IPv4Address, whenCreated, whenChanged, DistinguishedName,
        @{Name="MemberOf";Expression={($_.MemberOf -join ";")}} |
        ConvertTo-Csv -NoTypeInformation
        '''
        command_template = 'Remove-ADComputer -Identity "{}$" -Confirm:$false'
        inactivity_years = int(config["Computer"].get("computer_disabled_years", 1))
        
    elif intent == "disable":
        computer_ps = '''
        Get-ADComputer -Filter "Enabled -eq 'True'" -Properties IPv4Address, whenCreated, LastLogonDate, MemberOf, DistinguishedName |
        Select-Object Name, IPv4Address, whenCreated, LastLogonDate, DistinguishedName,
        @{Name="MemberOf";Expression={($_.MemberOf -join ";")}} |
        ConvertTo-Csv -NoTypeInformation
        '''
        command_template = 'Disable-ADAccount -Identity "{}$"'
        inactivity_years = int(config["Computer"].get("computer_years_since_logon", 10))
        

    def get_identifier(r):
        if "DistinguishedName" in r and r["DistinguishedName"]:
            return r["DistinguishedName"].strip()
        elif "Name" in r and r["Name"]:
            return r["Name"].strip()
        else:
            return None
        
    name_exclusion = config["Computer"].get("exclude_name_starting_with", "")
    bypass_group_pattern = config["Computer"].get("computer_bypass_group", "")
    exclude_if_has_ip = config["Computer"].get("exclude_computers_with_IPs", "true").lower() == "true"

    def bypass_condition(r):
        name = r.get("Name","").strip()
        groups = r.get("MemberOf", "")
        ip = r.get("IPv4Address", "").strip()
        
        name_match = name_exclusion and name.startswith(name_exclusion)
        group_match = re.search(bypass_group_pattern, groups)
        ip_check = exclude_if_has_ip and ip != ""
        
        return group_match or name_match or ip_check

    clean_ad_objects(
        ps_command=computer_ps,
        object_type="computer",
        intent=intent,
        inactivity_years=inactivity_years,
        get_identifier=get_identifier,
        bypass_condition=bypass_condition,
        command_template=command_template,
        filename_prefix="computer",
        dry_run=dry_run
    )





'''
##################################
Print various statistics about AD.
##################################

6/9/2025
'''
def ad_stats():
    print("")
    commands = {
        "TREES ": "$f = Get-ADForest; if ($f.Trees) { $f.Trees.Count } else { 1 }",
        "GPOs  ": "Get-GPO -All | Measure-Object | Select-Object -ExpandProperty Count",
        "OUs   ": "Get-ADOrganizationalUnit -Filter * | Measure-Object | Select-Object -ExpandProperty Count",
        "ENABLED  USERS": "Get-ADUser -Filter 'Enabled -eq $true' | Measure-Object | Select-Object -ExpandProperty Count",
        "DISABLED USERS": "Get-ADUser -Filter 'Enabled -ne $true' | Measure-Object | Select-Object -ExpandProperty Count",
        "ENABLED  COMPUTERS": "Get-ADComputer -Filter 'Enabled -eq $true' | Measure-Object | Select-Object -ExpandProperty Count",
        "DISABLED COMPUTERS": "Get-ADComputer -Filter 'Enabled -ne $true' | Measure-Object | Select-Object -ExpandProperty Count"
    }

    for label, ps_cmd in commands.items():
        output = run_powershell_command(ps_cmd).stdout.strip()
        print(f"{main_color}{label}: {RESET}{output}")

    recycle_bin_check_ps = '''
    $feature = Get-ADOptionalFeature -Filter {Name -eq "Recycle Bin Feature"}
    if ($feature.EnabledScopes.Count -gt 0) {
        Write-Output "ENABLED"
    } else {
        Write-Output "DISABLED"
    }
    '''
    recycle_bin_status = run_powershell_command(recycle_bin_check_ps).stdout.strip()
    print(f"{main_color}RECYCLE BIN:{RESET} {recycle_bin_status}")
    
    input(f"\nPress {main_color}ENTER{RESET} to continue.")




'''
##########################################
Confirm before proceeding with operations.
##########################################

5/30/2025
'''
def get_consent(dry_run):

    #Display if dry-run is enabled.
    if dry_run:
        print(f"\n\t{RED}###################################################################{RESET}")
        print(f"\t{RED}###{main_color}Dry Run Enabled:{RESET} These objects will {main_color}NOT{RESET} actually be affected.{RED}###{RESET}")
        print(f"\t{RED}###################################################################{RESET}\n")
    
    while True:
        answer = input("Proceed? (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            separator(main_color, RESET)
            return True
        elif answer in ("n", "no"):
            print("Well... it seems we are at an impass...")
            time.sleep(1)
            print(f"{main_color}Restarting...\n{RESET}")
            time.sleep(3)
            main()
            sys.exit()
        else:
            print("Please enter 'y' or 'n'\n")





'''
##################################
Run windowless PowerShell command.
##################################

5/30/2025
'''
def run_powershell_command(ps_command):
    result = subprocess.run(
        ["powershell", "-Command", ps_command],
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW
    )
    return result





'''
########################
Ensure RSAT is installed
########################

6/2/2025
'''
def verify_ad_tools():
    test_command = "Get-Command -Name Get-ADUser -ErrorAction SilentlyContinue"
    result = run_powershell_command(test_command)
    if not result.stdout.strip():
        print("\nAD Module not found. Is this a domained machine with RSAT installed and enabled?")
        time.sleep(5)
        print("EXITING")
        time.sleep(1)
        sys.exit(1)
        




'''
#######################
Print results to files.
#######################

6/2/2025
'''
def print_results(filename_prefix, intent, object_type, bypassed, affected):
    today = date.today().strftime("%Y-%m-%d")
    
    if bypassed:
        with open(f"{filename_prefix}s_bypassed_{today}.csv", 'w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=bypassed[0].keys())
            writer.writeheader()
            writer.writerows(bypassed)

    if affected:        
        with open(f"{filename_prefix}s_{intent.lower()}d_{today}.csv", 'w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=affected[0].keys())
            writer.writeheader()
            writer.writerows(affected)
    print(f"{main_color}OPERATIONS COMPLETED{RESET}")
    print(f"{len(bypassed)} {object_type}s bypassed.")
    print(f"{len(affected)} {object_type}s {intent.lower()}d.\n")
    print(f"List of bypassed {object_type}s saved in: {filename_prefix}_bypassed_{today}.csv")
    print(f"List of {intent.lower()}d {object_type}s saved in: {filename_prefix}_{intent.lower()}d_{today}.csv\n")

    print(f"Files saved to: {os.getcwd()}")
    input(f"\nPress {main_color}ENTER{RESET} to continue.")








    
r'''
                    #################################################
                    #  ____                         _   _           #
                    # / ___|___  ___ _ __ ___   ___| |_(_) ___ ___  #
                    #| |   / _ \/ __| '_ ` _ \ / _ \ __| |/ __/ __| #
                    #| |__| (_) \__ \ | | | | |  __/ |_| | (__\__ \ #
                    # \____\___/|___/_| |_| |_|\___|\__|_|\___|___/ #
                    #                                               #
                    #################################################
'''




# Add colors
RED = "\u001b[0;31m"
GREEN = "\u001b[0;32m"
CYAN = "\u001b[36m"
LIGHT_CYAN = "\u001b[1;36m"
RESET= "\u001b[0m"

COLOR_MAP = {
    "RED": RED,
    "GREEN": GREEN,
    "CYAN": CYAN,
    "LIGHT_CYAN": LIGHT_CYAN,
    "RESET":RESET
}


main_color_str = (config["Color"].get("main_color", LIGHT_CYAN)).upper()
main_color = COLOR_MAP.get(main_color_str, LIGHT_CYAN)





'''
#######################################################
Clear console and print pretty introduction to program.
#######################################################

5/29/2025
'''
def intro(color, reset, version_number):
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{color}\n")
    print(f"  █████╗ ██████╗      ██████╗██╗     ███████╗ █████╗ ███╗   ██╗███████╗██████╗ ")
    print(f" ██╔══██╗██╔══██╗    ██╔════╝██║     ██╔════╝██╔══██╗████╗  ██║██╔════╝██╔══██╗")
    print(f" ███████║██║  ██║    ██║     ██║     █████╗  ███████║██╔██╗ ██║█████╗  ██████╔╝")
    print(f" ██╔══██║██║  ██║    ██║     ██║     ██╔══╝  ██╔══██║██║╚██╗██║██╔══╝  ██╔══██╗")
    print(f" ██║  ██║██████╔╝    ╚██████╗███████╗███████╗██║  ██║██║ ╚████║███████╗██║  ██║")
    print(f" ╚═╝  ╚═╝╚═════╝      ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝{reset}")
    print(f"                                                                    Version {version_number}")





'''
#######################
Print options for user.
#######################

5/29/2025
'''
def main_option_list():
    print("\n\nEnter a number to clean active directory:")
    print("1) Toggle Dry Run")
    print("2) Clean  Inactive Users")
    print("3) Clean  Inactive Computers")
    print("4) Clean  Neither")
    print("5) Stats")
    print("\n0) Leave  Console")

    answer = input("\nChoice: ")
    return answer





'''
'''
def sub_option_list():
    print(f"\nWould you like to {main_color}DISABLE{RESET} or {main_color}DELETE{RESET} these objects from active directory?")
    print("1) DISABLE")
    print("2) DELETE")

    answer = input("\nChoice: ")
    return answer





'''
##############################################
Spinning cursor to show program didn't freeze.
##############################################

5/29/2025
'''
def spinner_task():
    spinner = "|/-\\"
    i = 0
    while not spinner_done.is_set():
        msg = f"\rCleaning... {spinner[i % len(spinner)]}"
        sys.stdout.write(msg)
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write("\r                \r")





'''
###################################################
Display whether or not the code is in dry run mode.
###################################################

6/5/2025
'''
def display_dry_run(dry_run):
    if dry_run:
        print(f"DRY RUN = {GREEN}ENABLED{RESET}")
    else:
        print(f"DRY RUN = {RED}DISABLED{RESET}")





'''
#######################################
Separate lines to increase readability.
#######################################

5/30/2025
'''
def separator(color, reset):
    terminal_width = shutil.get_terminal_size().columns
    print(f"{color}\n{'#'*terminal_width}\n{reset}")




          
if __name__ == "__main__":
    main()

