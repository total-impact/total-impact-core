import time
from provider import Provider, ProviderError, ProviderTimeout, ProviderServerError, ProviderClientError, ProviderHttpError, ProviderState, ProviderContentMalformedError, ProviderValidationFailedError
from totalimpact.models import MetricSnap
from BeautifulSoup import BeautifulStoneSoup
import requests

from totalimpact.tilogging import logging
logger = logging.getLogger(__name__)

class Wikipedia(Provider):  

    def __init__(self, config):
        super(Wikipedia, self).__init__(config)
        self.state = WikipediaState(config)
        self.id = self.config.id

    def sleep_time(self):
        sleep_length = self.state.sleep_time()
        logger.debug(self.config.id + ": sleeping for " + str(sleep_length) + " seconds")
        return sleep_length
    
    def member_items(self, query_string, query_type): 
        raise NotImplementedError()
    
    def aliases(self, item): 
        raise NotImplementedError()

    def provides_metrics(self): return True
    
    def metrics(self, item):
        try:
            ## FIXME.  Should this call Metrics __init__ somewhere to get initialized?
            
            # get the alias object out of the item
            alias_object = item.aliases
            logger.info(self.config.id + ": metrics requested for tiid:" + alias_object.tiid)
            
            # construct the metrics object based on queries on each of the 
            # appropriate aliases
            metric = MetricSnap(id=self.config.id)
            
            # get the aliases that we want to check
            aliases = alias_object.get_aliases_list(self.config.supported_namespaces)
            if aliases is None or len(aliases) == 0:
                logger.debug(self.config.id + ": No acceptable aliases in tiid:" + alias_object.tiid)
                logger.debug(self.config.id + ": Aliases: " + str(alias_object.get_aliases_dict()))
                return item
            
            # FIXME: this is broken
            # if there are aliases to check, carry on
            for alias in aliases:
                logger.debug(self.config.id + ": processing metrics for tiid:" + alias_object.tiid)
                logger.debug(self.config.id + ": looking for mentions of alias " + alias[1])
                metric = self._get_metrics(alias)
            
            # add the static_meta info and other bits to the metrics object
            metric.static_meta(self.config.static_meta)
            
            # log our success (DEBUG and INFO)
            logger.debug(self.config.id + ": final metrics for tiid " + alias_object.tiid + ": " + str(metric))
            logger.info(self.config.id + ": metrics completed for tiid:" + alias_object.tiid)
            
            # finally update the item's metrics object with the new one, and return the item
            item.metrics.add_metric_snap(metric)
            return item
        except ProviderError as e:
            # this is the ultimate error handling.  All error mitigation should be
            # done in the above code block (or called methods)
            self.error(e, item)
            return item
    
    def _get_metrics(self, alias):
        # FIXME: urlencoding?
        url = self.config.metrics['url'] % alias[1]
        this_metrics = MetricSnap(id=self.config.id)
        logger.debug(self.config.id + ": attempting to retrieve metrics from " + url)
        
        self._mitigated_get_metrics(url, this_metrics)
        
        sdurl = self.config.metrics['provenance_url'] % alias[1]
        this_metrics.provenance(sdurl)
        
        logger.debug(self.config.id + ": interim metrics: " + str(this_metrics))
        return this_metrics
    
    def _mitigated_get_metrics(self, url, this_metrics):
        retry = 0
        while True:
            # try to get a response from the data provider        
            response = self.http_get(url, timeout=self.config.metrics['timeout'], error_conf=self.config.errors)
            
            # client errors and server errors are not retried, as they usually 
            # indicate a permanent failure
            if response.status_code != 200:
                if response.status_code >= 500:
                    raise ProviderServerError(response)
                else:
                    raise ProviderClientError(response)
                    
            # NOTE: if there was a specific error which indicated rate-limit failure,
            # it could be caught here, and sent to the _snooze_or_raise method
            
            try:
                # construct the metrics
                self._extract_stats(response.text, this_metrics)
                return
            except ProviderContentMalformedError as e:
                self._snooze_or_raise("content_malformed", self.config.errors, e, retry)
            except ProviderValidationFailedError as e:
                self._snooze_or_raise("validation_failed", self.config.errors, e, retry)
            
            retry += 1
    
    def _extract_stats(self, content, metrics):
        try:
            soup = BeautifulStoneSoup(content)
        except:
            raise ProviderContentMalformedError("Content cannot be parsed into soup")
        
        try:
            articles = soup.search.findAll(title=True)
            metrics.value(len(articles))
        except AttributeError:
            # NOTE: this does not raise a ProviderValidationError, because missing
            # articles are not indicative of a formatting failure - there just might
            # not be any articles
            metrics.value(0)
            

class WikipediaState(ProviderState):
    
    def __init__(self, config):
        # need to init the ProviderState object counter
        if config.rate is not None:        
            super(WikipediaState, self).__init__(config.rate['period'], config['limit'])
        else:
            super(WikipediaState, self).__init__(throttled=False)
    
