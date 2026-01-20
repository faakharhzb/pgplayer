# pgplayer

**warning**: pgplayer is still in active developement. It is not recommended to use it as for now.

pgplayer is a python library that allows you to run videos in pygame(-ce). It uses ffmpeg to convert frames from a video into a pygame surface and plays audio using sounddevice.

## Installation

Install using this command:
```sh
pip install https://github.com/faakharhzb/pgplayer/archive/refs/heads/main.zip
```

## Dependencies

pgplayer is dependent on many external libraries and programs. It obviously needs pygame(-ce). It uses [ffmpeg](https://ffmpeg.org) to separate video and audio and convert the video into pygame frames, through [ffmpeg-python](https://github.com/kkroening/ffmpeg-python), which provides python bindings for ffmpeg. It uses [sounddevice](https://python-sounddevice.readthedocs.io/en/latest/) to play audio. And it also requires numpy to convert video frames into pygame surfaces and audio frames into playable buffers.

## Contributing

First, fork this repository. Then clone it:
```sh
git clone https://github.com/<your-name>/pgplayer.git
```

Then create a new branch:
```sh
git switch -c <branch-name>
```

After editing files, install the package using:
```sh
pip install -e .
```

Then, commit and push the changes to your repository:
```sh
git add .
git commit -m "<commit message>"
git push -u origin <branch-name>
```

Then, go to your fork of the repository and open a pull request. Make sure the pull request is detailed and precise.
