[![CI Status](https://github.com/kitzeslab/opensoundscape/workflows/CI/badge.svg)](https://github.com/kitzeslab/opensoundscape/actions?query=workflow%3ACI)
[![Documentation Status](https://readthedocs.org/projects/opensoundscape/badge/?version=latest)](http://opensoundscape.org/en/latest/?badge=latest)

# OpenSoundscape

OpenSoundscape is a utility library for analyzing bioacoustic data.
It consists of command line scripts for tasks such as preprocessing audio data,
training machine learning models to classify vocalizations, estimating the
spatial location of sounds, identifying which species' sounds are present in
acoustic data, and more.

These utilities can be strung together to create data analysis pipelines.
OpenSoundscape is designed to be run on any scale of computer:
laptop, desktop, or computing cluster.

OpenSoundscape is currently in active development. If you find a bug, please submit an issue. If you have another question about OpenSoundscape, please email Sam Lapp (`sam.lapp` at `pitt.edu`) or Tessa Rhinehart (`tessa.rhinehart` at `pitt.edu`).

For examples of some of the utilities offered, please see the "Tutorials" section of the [documentation](https://opensoundscape.org). Included are instructions on how to download and use a pretrained machine learning model from our publicly available set of models. We plan to add additional tutorials soon.

# Installation

OpenSoundscape can be installed either via pip (for users) or poetry (for
developers contributing to the code). Either way, Python 3.7 or higher is required.

## Installation via pip (most users)

### Just give me the pip command!

Already familiar with installing python packages via pip? The pip command to install OpenSoundscape is `pip install opensoundscape==0.4.5`.

### Linux and Mac installation
OpenSoundscape requires Python 3.7 and a variety of Python packages. You have several options for how to install these dependencies. We recommend installing OpenSoundscape in a virtual environment to prevent dependency conflicts. Below are demonstrations of creating a virtual environment containing OpenSoundscape using Anaconda or `venv`. 

For some of our functions, you will need a version of `ffmpeg >= 0.4.1`. On Mac machines, `ffmpeg` can be installed via `brew`.

#### Example 1: Anaconda

First, download Anaconda for your computer here: https://www.anaconda.com/products/individual. Follow instructions for installing Anaconda and adding it to your PATH. Then, open your bash terminal and run the following commands:
* Create a new virtual environment named `opensoundscape` containing Python 3.7. and `pip`: 

      conda create -n opensoundscape python=3.7 pip
      
* Activate the new environment 

      conda activate opensoundscape

* Use `pip` to install OpenSoundscape 
 
      pip install opensoundscape==0.4.5

#### Example 2: `venv` 
First, obtain Python 3.7 from [this website](https://www.python.org/downloads/). Then, run the following commands in your bash terminal:
* Check that you have installed Python 3.7.\_

      python3 --version
      
* Change directories to where you wish to store the environment. You can use this folder to store virtual environments for other projects as well, so put it somewhere that makes sense for you, e.g. in your home directory.

      cd [path for environments folder]
      
* Make a directory for virtual environments and `cd` into it

      mkdir .venv && cd .venv
      
* Create an environment called `opensoundscape` in the directory:

      python3 -m venv opensoundscape
      
* Activate/use the environment

      source opensoundscape/bin/activate
     
* Install OpenSoundscape in the environment

      pip install opensoundscape==0.4.5
      
* Once you are done with OpenSoundscape, deactivate the environment

      deactivate


To use the environment again, you will have to refer to absolute path of the virtual environments folder. For instance, if I were on a Mac and created `.venv` inside a directory `/Users/MyFiles/Code` I would activate the virtual environment using: `source /Users/MyFiles/Code/.venv/opensoundscape/bin/activate`

### Windows installation

The easiest way to install OpenSoundscape on a Windows computer is to use the Windows Subsystem for Linux (WSL). 

If you don't already use WSL (or don't know what it is):
* Open Powershell as administrator
* Copy and paste first command from https://docs.microsoft.com/en-us/windows/wsl/install-win10
* Restart computer

Once WSL is installed:
* Open Windows Store, search for "Ubuntu"
* Click "Ubuntu 20.04 LTS"
* Click "Get"
* Click "Install"
* Click "Launch"
* Set username and password to something you will remember
* `sudo apt update`

Next, download and initialize Anaconda (these are examples for one version of Anaconda; your commands may look slightly different):

* Get the most recent Anaconda link under the "Linux" section on this page: https://www.anaconda.com/products/individual
* Download Anaconda in WSL using wget, e.g. 

      wget https://repo.anaconda.com/archive/Anaconda3-2020.07-Linux-x86_64.sh
  
* Execute the downloaded file, e.g. 

      bash Anaconda3-2020.07-Linux-x86_64.sh
* Remove the downloaded file after installation, e.g.

      rm Anaconda3-2020.07-Linux-x86_64.sh

* Initialize your conda installation

      source ~/anaconda3/bin/activate
      conda init

* Close and open terminal window to have access to the initialized conda

Now create a `conda` environment for OpenSoundscape

* Create a Python 3.7 conda environment for OpenSoundscape:

      conda create -n opensoundscape python=3.7 pip
      
* Activate the environment

      conda activate opensoundscape
      
* Install opensoundscape using pip

      pip install opensoundscape==0.4.5

If you want to use OpenSoundscape in JupyterLab:
* Activate the environment
* Start JupyterLab from inside the conda environment: `jupyter lab`
* Copy and paste the link created into your browser


## Installation via poetry (Linux and Mac; contributors and advanced users)
Poetry installation allows direct use of the most recent version of the code.
This workflow allows advanced users to use the newest features in OpenSoundscape,
and allows developers/contributors to build and test their contributions.

To install via poetry, do the following:
* Download [poetry](https://poetry.eustace.io/docs/#installation)
* Download
  [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/install.html)
* Link `poetry` and `virtualenvwrapper`:
  - Figure out where the virtualenvwrapper.sh file is: `which virtualenvwrapper.sh`
  - Add the following to your `~/.bashrc` and source it.
    ```
    # virtualenvwrapper + poetry
    export PATH=~/.local/bin:$PATH
    export WORKON_HOME=~/Library/Caches/pypoetry/virtualenvs
    source [insert path to virtualenvwrapper.sh, e.g. ~/.local/bin/virtualenvwrapper_lazy.sh]
    ```
* **Users**: clone this github repository to your machine:
`git clone https://github.com/kitzeslab/opensoundscape.git`
* **Contributors**: fork this github repository and clone the fork to your machine
* Ensure you are in the top-level directory of the clone
* Switch to the development branch of OpenSoundscape: `git checkout develop`
* Build the virtual environment for opensoundscape: `poetry install`
  - If poetry install outputs the following error, make sure to download Python 3.7:
    ```
    Installing build dependencies: started
    Installing build dependencies: finished with status 'done'
    opensoundscape requires Python '>=3.7,<4.0' but the running Python is 3.6.10
    ```
    If you are using `conda`, install Python 3.7 using `conda install python==3.7`
  - If you are on a Mac and poetry install fails to install `numba`, contact one
    of the developers for help troubleshooting your issues.
* Activate the virtual environment with the name provided at install e.g.: `workon opensoundscape-dxMTH98s-py3.7` or `poetry shell`
* Check that OpenSoundscape runs: `opensoundscape -h`
* Run tests (from the top-level directory): `poetry run pytest`
* Go back to your system's Python when you are done: `deactivate`

### Jupyter
To use OpenSoundscape within JupyterLab, you will have to make an `ipykernel`
for the OpenSoundscape virtual environment.

- Activate poetry virtual environment, e.g.: `workon opensoundscape-dxMTH98s-py3.7`
    - Use `poetry env list` if you're not sure what the name of the environment is
- Create ipython kernel: `python -m ipykernel install --user --name=[name of poetry environment] --display-name=OpenSoundscape`
- Now when you make a new document on JupyterLab, you should see a Python kernel available called OpenSoundscape.
- Contributors: if you include Jupyter's `autoreload`, any changes you make to the source code
  installed via poetry will be reflected whenever you run the `%autoreload` line magic in a cell:
    ```
    %load_ext autoreload
    %autoreload
    ```

### Contributing to code

Make contributions by editing the code in your fork. Create branches
for features using `git checkout -b feature_branch_name` and push these
changes to remote using `git push -u origin feature_branch_name`. To merge a
feature branch into the development branch, use the GitHub
web interface to create a merge request.

When contributions in your fork are complete, open a pull request using the
GitHub web interface. Before opening a PR, do the following to
ensure the code is consistent with the rest of the package:
* Run tests: `poetry run pytest`
* Format the code with `black` style (from the top level of the repo): `poetry run black .`
  * To automatically handle this, `poetry run pre-commit install`
* Additional libraries to be installed should be installed with `poetry add`, but
  in most cases contributors should not add libraries.

### Contributing to documentation

Build the documentation using either poetry or sphinx-build
- With poetry: `poetry run build_docs`
- With sphinx-build: `sphinx-build doc doc/_build`
