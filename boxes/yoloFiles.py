import os

def loadFile(videoName):
    stem = os.path.splitext(os.path.basename(videoName))[0]
    box_path = os.path.join('boxes', stem + '.txt')
    print("Loading boxes from:", box_path)
    with open(box_path, "r") as f:
        lines = f.readlines()
    lines = [x.strip() for x in lines]
    lines.pop(0)

    temp = []
    res = []

    for l in lines:
        if l == '--':
            res.append(temp)
            temp = []
            continue
        x = l.split()
        if x[0] == 'traffic' or x[0] == 'fire' or x[0] == 'stop' or x[0] == 'parking' or x[0] == 'sports' or\
                x[0] == 'baseball' or x[0] == 'tennis' or x[0] == 'wine' or x[0] == 'hot' or x[0] == 'cell' or\
                x[0] == 'teddy' or x[0] == 'hair':
            x[0] = x[0] + x[1]
            x.pop(1)

        temp.append([x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])])
    if temp != []:
        res.append(temp)
    return res

# loadFile('videos/Easy.mp4')