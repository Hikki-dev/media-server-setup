# File sharing

For a Linux computer that you manage yourself and that does not run the setup page, or that already runs its own Samba.

The script Share folders on this computer.sh installs Samba if it is missing, creates one login, and shares the folders you list. Run it with sudo:

```
sudo bash "Share folders on this computer.sh" /mnt/Media /mnt/Backup
```

1. It asks you to choose a password for the share login. The login name is media. To use another name, start the command with SHARE_USER=yourname.
2. Every folder you list becomes one share named after the folder. Add --read-only before the folders to make them all read only.
3. Files made over the network belong to the user who ran sudo, so your other apps can use them. To choose another owner, start the command with SHARE_OWNER=thatuser.
4. Your old settings are saved next to the new file. Run the script again any time to change the list.
5. If you already share things with Samba, your own settings are kept and only the new shares are added.

It works on Debian and Ubuntu. For other systems, see the last part of docs/File sharing.md, which has the full settings to write by hand.

The whole guide, including how to prepare your drives and how to use the shares away from home, is in docs/File sharing.md.
