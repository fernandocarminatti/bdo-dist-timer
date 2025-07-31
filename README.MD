# Python Client-Server Application

This project is a simple client-server application. The server uses `asyncio` for handling connections, and the client is a `PyQt6` graphical application that also utilizes `pygame` and the `keyboard` library, for real-time input handling.

## Prerequisites

-   Python 3.7+
-   `pip` (Python package installer)
-   `git` (for cloning the repository)

## Installation

Follow these steps to set up the project environment.

**1. Clone the Repository**

First, clone this repository to your local machine using git.

```bash
git clone https://github.com/fernandocarminatti/bdo-dist-timer.git
cd bdo-dist-timer
```

**2. Create a Virtual Environment (Recommended)**

It's a best practice to create a virtual environment to keep project dependencies isolated.

```bash
# For Windows
python -m venv venv
venv\Scripts\activate

# For macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

**3. Install Dependencies**

Install all the required Python packages. The required packages are `PyQt6`, `pygame`, and `keyboard`.

You can install them all with a single command:

```bash
pip install PyQt6 pygame keyboard
```

Alternatively, from requirements.txt

```bash
pip install -r requirements.txt
```

> **Note on the `keyboard` library:**
> On Linux, this library requires root permissions to access low-level keyboard events. You may need to run the client script with `sudo -E`.

## Usage

You will need to run the server and the client in two separate terminal windows.

**1. Run the Server**

Open a terminal, navigate to the project directory, and start the server.

```bash
python server.py
```

The server will start and print a message indicating it is waiting for connections.

**2. Run the Client**

Open a second terminal, navigate to the project directory, and start the client application.

```bash
python client.py
```