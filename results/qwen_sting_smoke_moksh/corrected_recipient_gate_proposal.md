# Corrected recipient call and health rule 5

The saved raw call used `name: Bob` and omitted `to`. It was not a nested arguments wrapper. The same message was sent successfully to Bob on the next attempt, within the existing retry budget. No chat turn or verdict was lost.

The current checker fails this under rule 5 because it sees an empty recipient. The earlier registration treated that signature as evidence of the D9 wrapping fault; this example shows the signature is not exclusive to wrapping.

Proposal for approval: retain and report ordinary malformed model calls that recover within the existing game rules, and gate actual argument-unwrapping losses separately. Keep all other health and approach criteria. Apply the distinction to every cell, preserve the legacy FAIL report, and label the amended criterion as decided after observing this case. Do not change prompts, schema aliases, retries, or model settings.

Until approved: hold pushy_ep1_game3 at its saved checkpoint and do not launch game 4. The other seven game-3 setups continue.
