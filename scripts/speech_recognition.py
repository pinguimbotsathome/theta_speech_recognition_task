#!/usr/bin/env python3
import rospy
from theta_speech.srv import SpeechToText
from theta_speech.srv import QuestionAnswer
import rospkg
from std_msgs.msg import String
from std_msgs.msg import Empty
import time
from datetime import datetime
import xml.dom.minidom as parser
import unicodedata
import sys
import os
import Levenshtein

PACK_DIR = rospkg.RosPack().get_path("theta_speech_recognition_task")
LOG_DIR = os.path.join(PACK_DIR,"logs/")

tts_pub  = rospy.Publisher('/textToSpeech', String, queue_size=10)
face_pub = rospy.Publisher('/hri/affective_loop', String, queue_size=10)
hotword_pub = rospy.Publisher('/hotword_activate', Empty, queue_size=1)

QUESTIONS = os.path.join(PACK_DIR,"questions/Questions.xml")
QUESTION_FROM_FILE = True if len(sys.argv) > 1 else False

question_counter = 0

def log(text, log_name, print_text=False, show_time=True):
    now = datetime.now()

    with open(log_name, "a+") as log_file:
        log_text = now.strftime(f"[%H:%M:%S] {text}") if show_time else text
        log_file.write(f"{log_text}\n")

    if print_text:
        print(text)


def get_questions(file):
    doc = parser.parse(file)

    original_questions = dict()
    questions = dict()

    items = doc.getElementsByTagName("question")

    for item in items:
        original_question = item.getElementsByTagName("q")[0].firstChild.data

        # Convert to lowercase and remove the question mark
        question = original_question.lower()[:-1]
        question = remove_accents(question)

        # Edge cases
        question = question             \
            .replace("+", " plus")      \
            .replace("(", "")           \
            .replace(")", "")           \
            .replace(",", "")

        answer = item.getElementsByTagName("a")[0].firstChild.data

        original_questions[question] = original_question
        questions[question] = answer

    return questions, original_questions


def remove_accents(input_str):
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    only_ascii = nfkd_form.encode("ASCII", "ignore")
    output_str = only_ascii.decode("UTF-8")

    return output_str

def get_similar_string(original_question, questions, log_name):
    # Calculate the Levenshtein Distance between all questions
    min_distance = float("inf")
    similar_question = str()

    log("\tLD\tQuestion", log_name, show_time=False)

    for question in questions:
        distance = Levenshtein.distance(original_question, question)

        if distance < min_distance:
            min_distance = distance
            similar_question = question

        log(f"\t{distance}\t{question}", log_name, show_time=False)

    return similar_question


def predefined_question(question, log_name, questions, original_questions):
    log(f"Understood: {question}", log_name)

    try:
        answer = questions[question]

    except KeyError:
        log("Looking for similar questions...", log_name)

        question = get_similar_string(question, questions, log_name)
        answer = questions[question]


    original_question = original_questions[question]

    log(f"Question: {original_question}", log_name, print_text=False)
    log(f"Answer: {answer}", log_name, print_text=False)

    return answer


def open_question(question, log_name):
    log(f"Understood: {question}", log_name)

    rospy.wait_for_service("services/questionAnswering")
    question_answer = rospy.ServiceProxy("services/questionAnswering", QuestionAnswer)
    answer = question_answer(question)
    return answer.answer

def task_procedure(self):
    global question_counter
    now = datetime.now()

    log_dir = os.path.join(PACK_DIR,"logs/")
    log_name = now.strftime("log_%H_%M_%S.txt")
    log_name = os.path.join(log_dir,log_name)

    log("Starting Speech Recognition", log_name)

    questions, original_questions = get_questions(QUESTIONS)

    tts_pub.publish('what is your question?')
    face_pub.publish('littleHappy')
    time.sleep(5)
    
    rospy.logwarn("Waiting for a question")
    rospy.wait_for_service("services/speechToText")
    speech_to_text = rospy.ServiceProxy("services/speechToText", SpeechToText)
    text = speech_to_text()
    rospy.logwarn(text.text)
    question = text.text
    if question_counter < 2:
        answer = predefined_question(question, log_name, questions, original_questions)

    else:
        answer = open_question(question, log_name)
        
    tts_pub.publish(answer)

    if question_counter < 6:
        question_counter = question_counter + 1
        hotword_pub.publish()
    
            
if __name__ == "__main__":
    rospy.init_node("speech_recognition_task")

    rospy.Subscriber("hotword", Empty, task_procedure)

    while not rospy.is_shutdown():
        pass

