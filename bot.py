from itertools import filterfalse

import discord
import discord.utils

from fuzzywuzzy import process


class VasyukovObserver(discord.Client):

    def __init__(self, subscribers):
        super().__init__()
        self.trainer_nicknames = {}
        self.subscribers = subscribers

    async def update_trainer_nicknames(self):
        self.trainer_nicknames = {}
        for user in self.get_all_members():
            if self.can_consult(user):
                self.trainer_nicknames[str(user)] = user

    on_ready = update_trainer_nicknames
    on_guild_join = update_trainer_nicknames
    on_guild_remove = update_trainer_nicknames
    on_guild_update = update_trainer_nicknames

    ######################################################################
    # SECTION: Utility

    def user_for(self, **kwargs):
        return discord.utils.get(self.get_all_members(), **kwargs)

    def trainer_like(self, query):
        key, _ = process.extractOne(query, self.trainer_nicknames.keys())
        return self.trainer_nicknames[key]

    @staticmethod
    def can_consult(user):
        for role in user.roles:
            if role.name in ('staff', 'admin'):
                return True
        return False

    @staticmethod
    def is_consultation_room(value):
        return value.startswith('Консультационная')

    @staticmethod
    async def send_privately(message, user):
        channel = user.dm_channel
        if channel is None:
            channel = await user.create_dm()
        await channel.send(message)

    @staticmethod
    def validate_args(args, a=0, b=32, max_length=256):
        if len(args) < a or len(args) > b:
            return False

        for arg in args:
            if len(arg) > max_length:
                return False
        return True

    HELP = '''Оперативно доносит о визитах избранных преподавателей в голосовые консультационные.
    
Использование: `command ...arguments`
Команды регистронезависимы.
    
О `fuzzy` аргументах:
Обрабатываются не по принципу "равно", но "больше всего похоже".
Например: из всех никнеймов преподавателей на сервере И5, `wolf` больше всего похож на `Woolfer#1420`.
    
Команды:
`add fuzzy_nickname ...`
    Подписывает вас на указанных _преподавателей_.
    e.g. `add c3h6o#7390 wolf`
        
`del fuzzy_nickname ...`
    Отписывает вас от кого вы там хотите.
    e.g. `del norte clcos першин`
    
`help`
    Выводит вот это вот все.
'''

    READ_HELP = 'Вы неправы. Почитайте хелпарик (help).'

    ######################################################################
    # SECTION: Event handlers

    async def on_message(self, message):
        # Fires even for the bot's messages in direct channels
        if message.author.id == self.user.id:
            return

        async def send_goodbytes():
            await self.send_privately(self.READ_HELP, message.author)

        parts = message.content.split()
        command, args = parts[0].lower(), parts[1:]
        if command == 'add':
            if not self.validate_args(args, 1):
                await send_goodbytes()
                return

            await self.handle_add(message.author, args)
        elif command == 'del':
            if not self.validate_args(args, 1):
                await send_goodbytes()
                return

            await self.handle_del(message.author, args)
        elif command == 'help':
            if not self.validate_args(args):
                await send_goodbytes()
                return

            await self.handle_help(message.author)
        else:
            await send_goodbytes()

    async def on_voice_state_update(self, user, _, after):
        # !channel.join event
        if after.channel is None:
            return

        if not self.is_consultation_room(after.channel.name):
            return

        if not self.can_consult(user):
            return

        subscribers = await self.subscribers.list(user.id)
        for subscriber in subscribers:
            message = f'{user} замечен в канале `{after.channel.name}`'
            await self.send_privately(message,
                                      self.user_for(id=subscriber))

    async def handle_add(self, author, nicknames):
        subscribed_to = []
        for user in filter(None, map(self.trainer_like, set(nicknames))):
            if not self.can_consult(user):
                continue

            pushed = await self.subscribers.push(author.id, user.id)
            if pushed:
                subscribed_to.append(str(user))

        if len(subscribed_to) == 0:
            message = 'Вы либо уже на всех подписаны, ' + \
                      'либо мы таких не знаем:('
            await self.send_privately(message, author)
        else:
            message = 'Подписали вас на:\n' + \
                      '\n'.join(f'- {nickname}' for nickname
                                in subscribed_to)
            await self.send_privately(message, author)

    async def handle_del(self, author, nicknames):
        unsubscribed_from = []
        for user in filter(None, map(self.trainer_like, set(nicknames))):
            removed = await self.subscribers.remove(author.id, user.id)
            if removed:
                unsubscribed_from.append(str(user))

        if not unsubscribed_from:
            message = 'Вы неправы.'
            await self.send_privately(message, author)
        else:
            message = 'Отписали вас от:\n' + \
                      '\n'.join(f'- {nickname}' for nickname
                                in unsubscribed_from)
            await self.send_privately(message, author)

    async def handle_help(self, author):
        await self.send_privately(self.HELP, author)
