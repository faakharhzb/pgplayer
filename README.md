# pgplayer

**warning**: pgplayer is still in active developement. Expect to see all sorts of bugs.

pgplayer is a python library that allows you to run videos in pygame(-ce). It uses pyAV to convert frames from a video into a pygame surface and plays audio using sounddevice.

## Installation

Install using this command:
```sh
pip install https://github.com/faakharhzb/pgplayer/archive/refs/heads/main.zip
```

## Dependencies

1. [Python 3.x](https://www.python.org/)
2. [Pygame Community Edition](https://www.pyga.me/)
3. [Numpy](https://www.numpy.org/)
4. [PyAV](https://github.com/PyAV-Org/PyAV)
5. [sounddevice](https://python-sounddevice.readthedocs.io/en/latest/)

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
