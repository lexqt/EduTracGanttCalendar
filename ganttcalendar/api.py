from datetime import date
from pkg_resources import resource_filename

from trac.core import Component
from trac.config import IntOption
from trac.util.translation import domain_functions


__all__ = ['TracGanttCalendar']


add_domain, _, N_, gettext, ngettext, tag_ = \
    domain_functions('ganttcalendar', ('add_domain', '_', 'N_', 'gettext',
                                  'ngettext', 'tag_'))

month_tbl = {
    1: N_('January'),
    2: N_('February'),
    3: N_('March'),
    4: N_('April'),
    5: N_('May'),
    6: N_('June'),
    7: N_('July'),
    8: N_('August'),
    9: N_('September'),
    10: N_('October'),
    11: N_('November'),
    12: N_('December'),
}

weekdays = (
    N_('Monday'),
    N_('Tuesday'),
    N_('Wednesday'),
    N_('Thursday'),
    N_('Friday'),
    N_('Saturday'),
    N_('Sunday'),
)

date_format = '%Y-%m-%d' # ISO 8601

def add_months(year, month, months):
    month = month + months - 1
    nyear  = year + month / 12
    nmonth = month % 12 + 1
    return date(nyear, nmonth, 1)


class TracGanttCalendar(Component):

    first_day = IntOption('ganttcalendar', 'first_day', '0',
            doc='Begin of week: 0 == Sunday, 1 == Monday')

    def __init__(self):
        locale_dir = resource_filename(__name__, 'locale')
        add_domain(self.env.path, locale_dir)
