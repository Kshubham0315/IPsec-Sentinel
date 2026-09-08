class RuleEngine:

    def __init__(self):
        self.rules = []

    def register_rule(self, rule):
        self.rules.append(rule)

    def analyze(self, data):
        results = []

        for rule in self.rules:
            result = rule.evaluate(data)

            if result:
                results.append(result)

        return results
