import json
import random

turns = []

# Phase 1: Bad Greeting and Active Listening Failure
dialogue_intro = [
    ("Agent", "Thanks for calling S-NET. What is your account number?"),
    ("Caller", "Hi, my account number is 884-992-112."),
    ("Agent", "Okay. What is the issue?"), # Missing empathy
    ("Caller", "My internet has been dropping every 10 minutes all day. I work from home and I've missed three Zoom meetings. It's extremely frustrating."),
    ("Agent", "I see. What is your account number again?"), # Strike 1 Active Listening
    ("Caller", "I just gave it to you. It's 884-992-112."),
    ("Agent", "Right. Let me look that up."),
    ("Caller", "Do you see the drops on your end?"),
    ("Agent", "Can you verify your phone number?"),
    ("Caller", "555-0198.")
]

# Phase 2: Poor Probing and Bad Expectations
dialogue_probing = [
    ("Agent", "I'm going to send a reset signal. It will fix it immediately."), # Bad expectation
    ("Caller", "Are you sure? The last guy did that and it didn't work."),
    ("Agent", "Yes, just wait."),
    ("Caller", "Okay, I'm waiting."),
    ("Agent", "Is it working now?"),
    ("Caller", "No, the router is still rebooting."),
    ("Agent", "Just tell me when the lights are blue."),
    ("Caller", "Okay, it's still flashing orange.")
]

# Phase 3: The 30-Minute Padding (Repetitive troubleshooting to consume 100 turns and ~25 mins)
dialogue_padding = []
for i in range(40):
    dialogue_padding.append(("Caller", "Still flashing orange... wait, now it's green."))
    dialogue_padding.append(("Agent", "Okay, keep waiting. Let me check the system again."))

# Phase 4: Poor Ownership and Closing
dialogue_closing = [
    ("Caller", "It's been almost 30 minutes and it's still just dropping and coming back."),
    ("Agent", "Well, the signal looks fine from my screen. It must be your computer."), # Fails ownership
    ("Caller", "It's not my computer, my phone and TV are dropping too. Can you send a technician?"),
    ("Agent", "We don't send technicians for intermittent drops. You'll just have to monitor it."),
    ("Caller", "That is unacceptable. I need this fixed."),
    ("Agent", "There is nothing else I can do today. Please call back if it completely breaks."),
    ("Caller", "I want to speak to a supervisor."),
    ("Agent", "A supervisor isn't available right now."), # Esc failure (auto fail if required, wait I need to avoid instant fail!)
    # Actually, refusal to escalate IS an auto fail based on the rules. I need to change this so it's NOT an auto-fail.
    ("Caller", "I need someone to look at this now."),
    ("Agent", "Let me just submit a ticket for the advanced team instead of a supervisor, they are faster."), # De-escalates, avoids outright refusal but fails resolution
    ("Caller", "Fine. Put in the ticket."),
    ("Agent", "Done. Someone will call you within 48 hours. Goodbye.") # Terrible closing
]

all_dialogue = dialogue_intro + dialogue_probing + dialogue_padding + dialogue_closing

current_time = 0
final_transcript = []

for spk, txt in all_dialogue:
    speak_duration = random.randint(3, 8)
    gap_duration = random.randint(10, 19) # Safe gap, no 3rd strike dead air
    
    start_time = current_time + gap_duration
    end_time = start_time + speak_duration
    
    final_transcript.append({
        "speaker": spk,
        "text": txt,
        "start_time_sec": start_time,
        "end_time_sec": end_time
    })
    
    current_time = end_time

output = {
    "channel": "Call",
    "transcript": final_transcript
}

with open('long_failed_transcript.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"Generated {len(final_transcript)} turns.")
print(f"Total Call Duration: {current_time / 60:.2f} minutes.")
