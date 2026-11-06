"""The accuracy test set for change summaries, and the command that scores a judge.

The set holds true summaries of real commits of this repository and
summaries with a mistake planted in them. The command asks the judge the
settings choose about each one and reports, per kind of mistake, the
mistakes caught, the true summaries wrongly flagged and the share of
"cannot tell" answers.
"""
