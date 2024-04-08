# Usage

## Quick setup

Clone this repository into a directory on your local machine

```
$ git clone https://github.com/ads91/tower-hamlets-tennis-court-watcher.git
```

Ensure to have Python installed on your machine and install the dependencies defined in requirements.txt

```
$ python -m pip install -r requirements.txt --upgrade
```

Create a new directory in the cloned repository directory called ".secrets" - this is where passwords, authentication tokens etc will be stored.

Within the newly created .secrets directory, create a file called auth.json with the following structure

```
{
  "emails": {
    "address": "<YOUR_EMAIL_ADDRESS>@gmail.com",
    "password": "<YOUR_EMAIL_ADDRESS_PASSWORD>"
  },
  "text": {}
}
```

The email above will be that which dispatches available slot emails to recipients that will be defined later (in another file contained within the .secrets directory).

***Note**: you will need to enable your gmail account to have programmatic access to the account. It's advised that you **don't use your personal email address** as enabling programmatic access can introduce security vulnerabilities.*

***Note**: the application uses yagmail which has only been tested with gmail addresses, we can't promise stability with non-gmail addresses.*

Within the.secrets directory, create another file called emails.json with the following structure

```
{
  "slot_available": [
    "<EMAIL_RECIPIENT_1>",
    "<EMAIL_RECIPIENT_2>",
    "<EMAIL_RECIPIENT_3>",
    ...
  ],
  "sys_errors": [
    "<EMAIL_RECIPIENT_1>"
    ...
  ]
}
```

Those emails in the "slot_available" entry are those who will receive notifications for permissible slots when they become available.

Those emails in the "sys_errors" entry will recieve emails if/when the notification system has encountered en error and if/when the system is back up and running.

Navigate to the cloned repository (i.e. the directory this readme.md resides in) and run the application (it will run indefinitely)

```
$ python main.py
```

## Advanced setup

### Configuring permissible slot notifications

### Configuring the court type
