from django.dispatch import Signal
 
ticket_created = Signal(providing_args = ['ticket'])
