"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/public.py - All public facing views, eg non-staff (no authentication
                  required) views.
"""

from datetime import datetime
import urlparse

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import loader, Context, RequestContext
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt

from helpdesk import settings as helpdesk_settings
from helpdesk.forms import PublicTicketForm
from helpdesk.lib import send_templated_mail, text_is_spam
from helpdesk.models import Ticket, Queue, UserSettings

def homepage(request):
    if request.user.is_staff:
        try:
            if getattr(request.user.usersettings.settings, 'login_view_ticketlist', False):
                return HttpResponseRedirect(reverse('helpdesk_list'))
            else:
                return HttpResponseRedirect(reverse('helpdesk_dashboard'))
        except UserSettings.DoesNotExist:
            return HttpResponseRedirect(reverse('helpdesk_dashboard'))

    if request.method == 'POST':
        form = PublicTicketForm(request.POST, request.FILES)
        form.fields['queue'].choices = [('', '--------')] + [[q.id, q.title] for q in Queue.objects.filter(allow_public_submission=True)]
        if form.is_valid():
            if text_is_spam(form.cleaned_data['body'], request):
                # This submission is spam. Let's not save it.
                return render_to_response('helpdesk/public_spam.html', RequestContext(request, {}))
            else:
                ticket = form.save()
                return HttpResponseRedirect('%s?ticket=%s&email=%s'% (
                    reverse('helpdesk_public_view'),
                    ticket.ticket_for_url,
                    ticket.submitter_email)
                    )
    else:
        try:
            queue = Queue.objects.get(slug=request.GET.get('queue', None))
        except Queue.DoesNotExist:
            queue = None
        initial_data = {}
        if queue:
            initial_data['queue'] = queue.id

        if request.user.is_authenticated() and request.user.email:
            initial_data['submitter_email'] = request.user.email

        form = PublicTicketForm(initial=initial_data)
        form.fields['queue'].choices = [('', '--------')] + [[q.id, q.title] for q in Queue.objects.filter(allow_public_submission=True)]

    return render_to_response('helpdesk/public_homepage.html',
        RequestContext(request, {
            'form': form,
            'helpdesk_settings': helpdesk_settings,
        }))


def view_ticket(request):
    ticket_req = request.GET.get('ticket', '')
    ticket = False
    email = request.GET.get('email', '')
    error_message = ''

    if ticket_req and email:
        parts = ticket_req.split('-')
        queue = '-'.join(parts[0:-1])
        ticket_id = parts[-1]

        try:
            ticket = Ticket.objects.get(id=ticket_id, queue__slug__iexact=queue, submitter_email__iexact=email)
        except:
            ticket = False
            error_message = _('Invalid ticket ID or e-mail address. Please try again.')

        if ticket:

            if request.user.is_staff:
                redirect_url = reverse('helpdesk_view', args=[ticket_id])
                if request.GET.has_key('close'):
                    redirect_url += '?close'
                return HttpResponseRedirect(redirect_url)

            if request.GET.has_key('close') and ticket.status == Ticket.RESOLVED_STATUS:
                from helpdesk.views.staff import update_ticket
                # Trick the update_ticket() view into thinking it's being called with
                # a valid POST.
                request.POST = {
                    'new_status': Ticket.CLOSED_STATUS,
                    'public': 1,
                    'title': ticket.title,
                    'comment': _('Submitter accepted resolution and closed ticket'),
                    }
                if ticket.assigned_to:
                    request.POST['owner'] = ticket.assigned_to.id
                request.GET = {}

                return update_ticket(request, ticket_id, public=True)

            return render_to_response('helpdesk/public_view_ticket.html',
                RequestContext(request, {
                    'ticket': ticket,
                    'helpdesk_settings': helpdesk_settings,
                }))

    return render_to_response('helpdesk/public_view_form.html',
        RequestContext(request, {
            'ticket': ticket,
            'email': email,
            'error_message': error_message,
            'helpdesk_settings': helpdesk_settings,
        }))

@csrf_exempt
def contactform(request):
    if request.method == 'POST':
        post = request.POST.copy()
        post['queue'] = 2 # sales
        post['priority'] = 5
        form = PublicTicketForm(post, {})
        form.fields['queue'].choices = [('', '--------')] + [[q.id, q.title] for q in Queue.objects.filter(allow_public_submission=True)]
        if form.is_valid():
            if text_is_spam(form.cleaned_data['body'], request):
                # This submission is spam. Let's not save it.
                return render_to_response('helpdesk/public_spam.html', RequestContext(request, {}))
            else:
                ticket = form.save()
                # Return to thank you page on refering page, if known
                if 'HTTP_REFERER' in request.META:
                    return HttpResponseRedirect(urlparse.urljoin(request.META['HTTP_REFERER'], '/contact-thank-you.html'))
                    
                else:
                    return HttpResponseRedirect('/contact-thank-you.html')
        else:
            return HttpResponse(str(form.errors));

    else:
        return HttpResponse('POST!');
