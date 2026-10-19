# Managing the apps in Portainer

Portainer is a web page for managing Docker. If you use it, keep every app in a Portainer stack, so you can see, start, stop and update them in one place. This page explains how, and the mistakes to avoid. Every point here came from a real problem.

## Put the generated stack in Portainer

1. The setup writes a file called `docker-compose.yml` in your stack folder (the one shown on the final page).
2. In Portainer open **Stacks**, press **Add stack**, choose **Web editor**, paste the file, and give the stack a name.
3. Add any secrets as **Environment variables** below the editor, not inside the file. Portainer passes them in. The setup keeps the NordVPN login in a separate file for the same reason, so move those two values into Portainer variables.

Good to know:

| Rule | Why |
|---|---|
| Use one stack per family of apps, for example one for the media apps and one for extras | A problem in one stack does not stop the others |
| Give containers a fixed `container_name` | Other apps and scripts find them by name |
| Put limits in the stack file, for example `cpus: 3.5` for Jellyfin | A limit set by hand with `docker update` is lost when the container is recreated |
| Keep your data in bind mounts on your drives | Recreating a container never touches them |

## Changing a stack: what really happens

When you press **Update the stack**, Portainer removes the stack's containers and creates them again, then starts them. That takes a minute or two, and every app in that stack is down meanwhile. Do it when nobody is watching.

If the creating step fails, the containers are left **Created but not started**. Everything in that stack stays down, and it looks fine in Portainer until you open the list. After every update, check:

```
docker ps -a --format "{{.Names}} {{.Status}}" | grep -v " Up "
```

If it prints anything, start those containers with `docker start name`, then find the reason in the Portainer log: `docker logs portainer --since 10m | grep -i error`.

## The most common reason an update fails

**A container with the same name already exists outside the stack.** Docker allows one container per name. If you ever started an app by hand with `docker run`, and the stack also defines it, the stack cannot create it and the whole update stops.

Find them: containers that have no `com.docker.compose.project` label are not in any stack.

```
docker ps -a --format "{{.Names}}" | while read n; do
  [ -z "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' $n)" ] && echo "$n is not in a stack"
done
```

To bring one into its stack: stop and remove the loose container, then update the stack. Your data stays, because it lives in the bind mounts.

## Other things that stop an update

| Message | Fix |
|---|---|
| `Network ... Resource is still in use` while removing | Another stack uses that network. It is only a warning. The network stays. |
| `the attribute version is obsolete` | Only a warning. Delete the `version:` line at the top. |
| `port is already allocated` | Something else uses that port. Change the left number in `ports:`. |
| A stack shows `Error` | Open the stack, press **Update the stack** again after fixing the cause above, and it turns green. |

## Images and updates

Portainer can show whether an image is up to date. Some registries answer it with an error, which is harmless. To update an app, press **Update the stack** and tick **Re-pull image**. Do this one stack at a time, and check each with the command above.

Do not update the stack that holds your business or database apps during working hours.

## Backups

Portainer keeps stack files in its own data folder. Back that folder up, together with the folders you keep your app settings in. The setup's own backup does not include Portainer.
