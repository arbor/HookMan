"""
Mapping module.

Self contained object to encapsulate all the mapping functionality
"""

import jinja2

class Mapping():

    """
    Constructor
    """
    def __init__(self, logger):
        self.logger = logger

    def substitute(self, format, template):
        """
        Recursively substitute a data structure

        :param format: data derived from the incoming request - all the fields that can be used in substitution
        :param template: template selected form the configuration file

        :return: the substituted data structure
        """

        result = None

        try:

            if isinstance(template, dict):
                result = {}
                for key, value in template.items():
                    result[key] = self.substitute(format, value)

                assert id(result) != id(template)

            elif isinstance(template, list):
                result = []
                for item in template:
                    result.append(self.substitute(format, item))

                assert id(result) != id(template)

            else:
                t = jinja2.Template(template)
                result = t.render(format)

        except (jinja2.exceptions.UndefinedError, jinja2.exceptions.TemplateSyntaxError) as e:
            self.logger.warning("Error in rendering: %s", template)
            self.logger.warning("%s", e)
            result = template

        return result

    def map(self, format, incoming):
        """
        Perform the mapping

        Take input in the form of the incoming URL, headers and payload, and map
        to the outgoing format using the formatting rules supplied

        :param format: The format strings to be used
        :param incoming: data form the incoming request

        :return: tuple with entries for the mapped url, headers and payload
        """

        new_url = None
        new_headers = None
        new_payload = None

        if "url" in format:
            new_url = self.substitute(incoming, format["url"])
        if "headers" in format:
            new_headers = self.substitute(incoming, format["headers"])
        if "payload" in format:
            new_payload = self.substitute(incoming, format["payload"])

        return new_url, new_headers, new_payload

