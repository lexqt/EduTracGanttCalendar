from setuptools import setup

extra = {} 
try:
    from trac.util.dist import get_l10n_cmdclass
    cmdclass = get_l10n_cmdclass()
    if cmdclass:
        extra['cmdclass'] = cmdclass
        extractors = [
            ('**.py',                'python', None),
            ('**/templates/**.html', 'genshi', None),
            ('**/templates/**.txt',  'genshi', {
                'template_class': 'genshi.template:NewTextTemplate',
            }),
        ]
        extra['message_extractors'] = {
            'ganttcalendar': extractors,
        }
except ImportError:
    pass

PACKAGE = 'ganttcalendar'

setup(
    name='EduTracGanttCalendar', version='1.0.0',
    packages=[PACKAGE],

    author = "Takashi Okamoto, Aleksey A. Porfirov",
    author_email='lexqt@yandex.ru',
    url="https://github.com/lexqt/EduTracGanttCalendar",
    description='Provide start/end date ticket fields, calendar and ganttchart.',
    license = "New BSD",

    entry_points={'trac.plugins': '%s = %s' % (PACKAGE, PACKAGE)},
    package_data={PACKAGE: ['templates/*.html','htdocs/img/*', 'htdocs/js/*', 'htdocs/css/*', 'locale/*.*','locale/*/LC_MESSAGES/*.*']},
    **extra)

#### AUTHORS ####
## Author of original TracGanttCalendarPlugin:
## Takashi Okamoto
## http://sourceforge.jp/projects/shibuya-trac/
## okamototk@user.sourceforge.jp
##
## Author of EduTrac adaptation and a lot of fixes and enhancements:
## Aleksey A. Porfirov
## lexqt@yandex.ru
## github: lexqt

