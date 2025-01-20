from datetime import datetime, timedelta
import subprocess
from PIL import Image

def create_commit(date: datetime):
    dateStr = date.strftime("%a %b %d %I:%M %Y +0700")
    with open("test.txt", "a") as f:
        f.write("aaaaa")
    subprocess.run(["git", "add", "test.txt"])
    subprocess.run(["git", "commit", "-m", "some stuff",])
    subprocess.run(["git", "commit", "--amend", "-m", "some stuff", f'--date="{dateStr}"',])
    
def create_commits_for_date(numCommits: int, date: datetime):
    dateStr = date.strftime("%a %b %d %I:%M %Y +0700")
    print(f"Creating {numCommits} on {dateStr}")
    for _ in range(numCommits):
        create_commit(date)

def get_start_date():
    # for instance - from Weds oct. 30 2024, start is Monday Oct 29 2023
    # get most recent Monday
    today = datetime.today()
    monday = today - timedelta(days=today.weekday())
    start_date = monday - timedelta(weeks=52, days=1) # hahA GOOD LUCK IF THIS IS NOT A LEAP YEAR :)
    return start_date

def read_image(img_name):
    im = Image.open(img_name).convert('L')
    imageSizeW, imageSizeH = im.size

    # x index is week number (0 being 52 weeks ago).
    # y index is day of week.
    pixels_to_color = []

    for i in range(imageSizeW):
        for j in range(imageSizeH):
            pixVal = im.getpixel((i, j))
            avg_darkness = (255 - pixVal)

            # 256 is ALMOST divisible by 5 :)
            green_level = int(avg_darkness / 51)

            if green_level > 0:
                pixels_to_color.append((i, j, green_level))

    return pixels_to_color

def get_commit_date(startDate, weeks, day):
    return startDate + timedelta(weeks=weeks, days=day)

def main(img_name):
    base_date = get_start_date()
    print(f"Base date: {base_date}")
    pixels = read_image(img_name)
    print("Pixels: ", pixels)
    for p in pixels:
        week_offset, day, num_commits = p
        commit_date = get_commit_date(base_date, week_offset, day)
        print(f"Commit date: {commit_date.strftime('%m-%d-%Y')}, commits: {num_commits}")
        create_commits_for_date(num_commits, commit_date)

if __name__ == "__main__":
    main('template.png')