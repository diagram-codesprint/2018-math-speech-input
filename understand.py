from flask import Flask, session, redirect, url_for, render_template, request, abort
import wolframalpha
import requests
app = Flask(__name__)
app.secret_key = "any random string"
appId = "PYJPPL-7RXKKAPT62"
client = wolframalpha.Client(appId)
mathMLEndpoint = "https://api.mathmlcloud.org/equation"
mostRecentStep = 0
steps = []
responses = []

def text2int(textnum, numwords={}):
  if not numwords:
    units = [
      "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
      "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
      "sixteen", "seventeen", "eighteen", "nineteen",
    ]

    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    scales = ["hundred", "thousand", "million", "billion", "trillion"]

    numwords["and"] = (1, 0)
    for idx, word in enumerate(units):    numwords[word] = (1, idx)
    for idx, word in enumerate(tens):     numwords[word] = (1, idx * 10)
    for idx, word in enumerate(scales):   numwords[word] = (10 ** (idx * 3 or 2), 0)

  current = result = 0
  for word in textnum.split():
      if word not in numwords:
        raise Exception("Illegal word: " + word)

      scale, increment = numwords[word]
      current = current * scale + increment
      if scale > 100:
          result += current
          current = 0

  return result + current

def isNumber(numberString):
  try:
    text2int(numberString)
    return True
  except:
    return False

def search(text='', mode='math'):
  text = text.lower()
  global mostRecentStep
  global responses
  words = text.split(' ')

  if words[0] == "recall":
    for word in words:
      if isNumber(word) and text2int(word) <= mostRecentStep:
        if "sorry" in responses[-1].lower():
          responses = responses[:-1]
        responses.append("Step " + str(text2int(word)) + " was " + steps[text2int(word)-1])
        return
      elif isNumber(word):
        if "sorry" in responses[-1].lower():
          responses = responses[:-1]
        responses.append("Sorry, that step does not exist")
        return
    if "last" in text or "recent" in text or "previous" in text:
      if "sorry" in responses[-1].lower():
        responses = responses[:-1]
      responses.append("Step " + str(mostRecentStep) + " was " + steps[-1])
      return
    else:
      if "sorry" in responses[-1].lower():
        responses = responses[:-1]
      responses.append("Sorry, I did not understand")
      return

  if words[0] == 'step' and isNumber(words[1]) and text2int(words[1]) > mostRecentStep:
    text = ' '.join(words[2:])
    mostRecentStep = text2int(words[1])
  else:
    mostRecentStep = mostRecentStep + 1

  words = text.split(' ')
  if words[0] == "copy":
    for word in words:
      if isNumber(word) and text2int(word) < mostRecentStep:
        if "sorry" in responses[-1].lower():
          responses = responses[:-1]
        responses.append("Step " + str(mostRecentStep) + ": " + steps[text2int(word)-1])
        steps.append(steps[text2int(word)-1])
        return
      elif isNumber(word):
        if "sorry" in responses[-1].lower():
          responses = responses[:-1]
        mostRecentStep = mostRecentStep - 1
        responses.append("Sorry, that step does not exist")
        return
    if "last" in text or "recent" in text or "previous" in text:
      if "sorry" in responses[-1].lower():
        responses = responses[:-1]
      responses.append("Step " + str(mostRecentStep) + ": " + steps[-1])
      steps.append(steps[-1])
      return

  if words[0] == 'compute':
    mode = 'answer'
    text = ' '.join(words[1:])

  words = text.split(" ")
  for i in range(len(words)):
    if words[i] == "step" and isNumber(words[i+1]) and text2int(words[i+1]) < mostRecentStep:
      stringToBeReplaced = words[i] + " " + words[i+1]
      text = text.replace(stringToBeReplaced, "open paren " + steps[text2int(words[i+1])-1] + " close paren", 1)
      print(text)
    elif words[i] == "step":
      if "sorry" in responses[-1].lower():
        responses = responses[:-1]
      responses.append("Sorry, I can't find that step you referenced. Please try again.")
      mostRecentStep = mostRecentStep - 1

  res = client.query(text)
  # Wolfram cannot resolve the question
  if res['@success'] == 'false':
    if "sorry" in responses[-1].lower():
      responses = responses[:-1]
    responses.append("Sorry, I didn't understand. Try again.")
    mostRecentStep = mostRecentStep - 1

  # Wolfram was able to resolve question
  else:
    result = ''
    # pod[0] is the question
    pod0 = res['pod'][0]
    # pod[1] may contains the answer
    pod1 = res['pod'][1]
    # checking if pod1 has primary=true or title=result|definition
    if mode == 'answer' and (('definition' in pod1['@title'].lower()) or ('result' in  pod1['@title'].lower()) or (pod1.get('@primary','false') == 'true')):
      # extracting result from pod1
      result = resolveListOrDict(pod1['subpod'])
      if "sorry" in responses[-1].lower():
        responses = responses[:-1]
      responses.append("Step " + str(mostRecentStep) + ": =" + result)
      steps.append(result)
    elif mode == 'answer':
      if "sorry" in responses[-1].lower():
        responses = responses[:-1]
      responses.append("Sorry, I couldn't compute. Try again.")
      mostRecentStep = mostRecentStep - 1
    else:
      # extracting wolfram question interpretation from pod0
      question = resolveListOrDict(pod0['subpod'])
      # removing unnecessary parenthesis
      # question = removeBrackets(question)

      if 'equals' not in text.lower() and '=' in question:
        question = question.split('=', 1)[0]
        if "sorry" in responses[-1].lower():
          responses = responses[:-1]
      responses.append("Step " + str(mostRecentStep) + ": " + question)
      steps.append(question)
      """
      data = {
        "components": [],
        "math": steps[-1],
        "mathType": "AsciiMath",
        "svg": True,
        "png": True,
        "Description": True,
        "mml": True,
      }
      headerParams = {"Content-Type": application/json}
      r = requests.post(url = mathMLEndpoint, data = data, headers = headerParams)
      print(r)
      cloudUrl = r.json()["cloudUrl"]
      getRequest = requests.get(url = cloudUrl)
      getResponse = getRequest.json()
      print(getResponse)
      """

def resolveListOrDict(variable):
  if isinstance(variable, list):
    return variable[0]['plaintext']
  else:
    return variable['plaintext']

def removeBrackets(variable):
  return variable.split('(')[0]

@app.route('/')
def index():
  return render_template('understand.html')

@app.route('/sendtext',methods = ['POST', 'GET'])
def sendtext():
  global responses
  if request.method == 'POST':
    if len(request.form['text']) > 0:
      search(request.form['text'])
      session['responses'] = responses
  print(responses)
  return render_template('understand.html', responses = responses)

if __name__ == '__main__':
   app.run(debug = True)
