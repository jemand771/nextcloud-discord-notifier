import os

from discord_webhook import DiscordEmbed, DiscordWebhook

from model import EventData


def send_message(embeds):
    hook = DiscordWebhook(os.environ.get("DISCORD_WEBHOOK"))
    for embed in embeds:
        hook.add_embed(embed)
    return hook.execute()


def create_event_embed(data: EventData):
    desc = language_format(
        actor=data.display_name,
        action=data.action,
        file=f"{markdown_link(data.file_name, data.file_url)}",
        folder=f"{markdown_link(data.file_dir, data.folder_url)}"
    )

    embed = DiscordEmbed(
        color=action_to_color(data.action),
        title=data.file_name,
        url=data.file_url,
        description=desc,
        timestamp=data.iso_timestamp
    )
    embed.set_footer(text=f"id: {data.key}")

    for field in data.additional_info or []:
        embed.add_embed_field(**field)

    embed.set_author(name=data.user_name)
    return embed


def language_format(actor, action, file, folder):
    # this is only split up because PyCharm would weirdly reformat it otherwise
    lang_dict = {
        "file_created": f"{actor} created {file} inside {folder}.",
        "file_deleted": f"{actor} deleted {file} from {folder}.",
        "file_changed": f"{actor} edited {file} in {folder}.",
    }
    return lang_dict.get(action) or f"ERR_LANG_FMT {actor=}, {action=}, {file=}, {folder=}"


def markdown_link(text, url):
    if not url:
        return f"`{text}`"
    return f"[{text}]({url})"


def action_to_color(action):
    return rgb_hex_to_dec(
        {
            "file_created": "#00ff00",
            "file_deleted": "#ff0000",
            "file_changed": "#ffff00"
        }[action]
    )


def rgb_hex_to_dec(code):
    r, g, b = [int(code[i:i + 2], 16) for i in range(1, 7, 2)]
    return 256 ** 2 * r + 255 * g + b
