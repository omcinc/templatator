import json
import os
import re

import logging
import mandrill

api_key_var = 'MANDRILL_API_KEY'
backup_dir_var = 'MANDRILL_BACKUP_DIR'
macro_template_slug_prefix = "macro-"

logger = logging.getLogger('mandrill_expanded')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

if not api_key_var in os.environ:
    raise Exception('Global variable not defined: ' + api_key_var)

if not backup_dir_var in os.environ:
    raise Exception('Global variable not defined: ' + backup_dir_var)

mandrill_client = mandrill.Mandrill(os.environ[api_key_var])
backup_dir = os.environ[backup_dir_var]

if not os.path.isdir(backup_dir):
    raise Exception('Backup directory not found: ' + backup_dir)

macro_name_regex = '[0-9A-Za-z._-]+'
macro_delimiter_pattern = re.compile('<!-- +macro-(begin|end) +(' + macro_name_regex + ') +-->')


class MacroException(Exception):
    pass


def find_macros(text, stack):
    begin_match = None
    macro_infos = []
    for match in macro_delimiter_pattern.finditer(text):
        tag = match.group(1)
        if tag == 'begin':
            if begin_match:
                raise MacroException(
                    'macro-begin without a matching macro-end' + stack_location(stack) + ': ' + begin_match.group(0))
            begin_match = match
        else:
            if not begin_match:
                raise MacroException(
                    'macro-end without a matching macro-begin' + stack_location(stack) + ': ' + match.group(0))
            macro_name = begin_match.group(2)
            if macro_name != match.group(2):
                raise MacroException('macro name mismatch' + stack_location(stack) + ': ' + begin_match.group(
                    0) + ' is matched by ' + match.group(0))
            macro_info = {'name': macro_name, 'begin': begin_match.start(0), 'end': match.end(0),
                          'content_begin': begin_match.end(0), 'content_end': match.start(0)}
            macro_infos.append(macro_info)
            begin_match = None
    if begin_match:
        raise MacroException(
            'macro-begin without a matching macro-end' + stack_location(stack) + ': ' + begin_match.group(0))
    return macro_infos


def stack_location(stack):
    if stack:
        return ' in macro ' + ' => '.join(list(map(lambda name: '"' + name + '"', stack)))
    else:
        return ''


def expand_macros(text, macro_dict, stack, keep_delimiters):
    macro_infos = find_macros(text, stack)
    result = ''
    start = 0
    for macro_info in macro_infos:
        macro_name = macro_info['name']
        new_stack = stack[:]
        new_stack.append(macro_name)
        if macro_name in stack:
            raise MacroException('circular macro reference: ' + ' => '.join(new_stack))
        value = macro_dict[macro_name]
        if not value:
            raise MacroException('undefined macro' + stack_location(stack) + ': ' + macro_name)
        expanded_value = expand_macros(value, macro_dict, new_stack, False)
        if keep_delimiters:
            index_start = 'content_begin'
            index_end = 'content_end'
        else:
            index_start = 'begin'
            index_end = 'end'
        result = result + text[start:macro_info[index_start]] + expanded_value
        start = macro_info[index_end]
    result = result + text[start:]
    return result


def fetch_templates(slugs=None):
    logger.info('Fetching templates')
    all_templates = mandrill_client.templates.list()
    templates = []
    macro_dict = {}
    for template in all_templates:
        slug = template['slug']
        if slug.startswith(macro_template_slug_prefix):
            macro_name = slug[len(macro_template_slug_prefix):]
            macro_dict[macro_name] = template['code']
        else:
            templates.append(template)
    not_found = []
    if slugs:
        templates = list(filter(lambda template: template['slug'] in slugs, templates))
        found_slugs = template_slugs(templates)
        for slug in slugs:
            if not slug in found_slugs:
                not_found.append(slug)
    return {'templates': templates, 'macros': macro_dict, 'not_found': not_found}


def expand_templates(templates, macro_dict):
    expanded_list = []
    error_list = []
    for template in templates:
        slug = template['slug']
        code = template['code']
        if code:
            logger.info('Expanding template: %s', slug)
            try:
                expanded_code = expand_macros(code, macro_dict, [], True)
                if expanded_code != code:
                    logger.info('Template is changed: %s', slug)
                    expanded_list.append({'template': template, 'new_code': expanded_code})
            except MacroException as excep:
                logger.info('An error occurred: %s: %s', slug, str(excep))
                error_list.append({'template': template, 'message': str(excep)})
        else:
            logger.info('Template has no code: %s', slug)
    return {'expanded': expanded_list, 'errors': error_list}


def save_template_drafts(expanded_list):
    backup_templates(list(map(lambda info: info['template'], expanded_list)))
    for expanded in expanded_list:
        template = expanded['template']
        slug = template['slug']
        new_code = expanded['new_code']
        logger.info('Saving expanded template draft: %s', slug)
        mandrill_client.templates.update(slug, code=new_code, publish=False)


def publish_templates(slugs):
    for slug in slugs:
        logger.info('Publishing template: %s', slug)
        mandrill_client.templates.publish(slug)


def backup_templates(templates):
    if not templates:
        return
    i = 0
    while os.path.exists(backup_dir_path(i)):
        i += 1
    dir = backup_dir_path(i);
    logger.info('Backing up %s templates: %s', len(templates), dir)
    os.mkdir(dir)
    for template in templates:
        file = dir + "/" + template['slug'] + ".json"
        with open(file, 'w') as outfile:
            json.dump(template, outfile)


def backup_dir_path(i):
    return backup_dir + ("/backup.%s" % i);


def draft_templates(templates):
    return list(filter(lambda template: template['publish_code'] != template['code'], templates))


def template_slugs(templates):
    return list(map(lambda template: template['slug'], templates))


###
### Public API
###

def expand_all(slugs=None, save_drafts=False):
    logger.info("== expand_all(save_drafts=%s)", save_drafts)
    template_info = fetch_templates(slugs=slugs)
    templates = template_info['templates']
    error_messages = []
    macro_dict = template_info['macros']
    expansion_result = expand_templates(templates, macro_dict)
    for error in expansion_result['errors']:
        error_messages.append(
            'Error during the expansion of template "%s": %s' % (error['template']['slug'], error['message']))
    expanded = expansion_result['expanded']
    if save_drafts:
        save_template_drafts(expanded)
    expanded_slugs = list(map(lambda exp: exp['template']['slug'], expanded))
    return {'total_count': len(templates), 'expanded': expanded_slugs, 'errors': error_messages,
            'not_found': template_info['not_found']}


def draft_list(slugs=None):
    logger.info("== draft_list()")
    template_info = fetch_templates(slugs=slugs)
    drafts = template_slugs(draft_templates(template_info['templates']))
    return {'drafts': drafts, 'not_found': template_info['not_found']}


def publish(slugs=None):
    logger.info("== publish_all()")
    template_info = fetch_templates(slugs=slugs)
    drafts = template_slugs(draft_templates(template_info['templates']))
    publish_templates(drafts)
    return {'published': drafts, 'errors': template_info['not_found']};
