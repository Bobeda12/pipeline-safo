# -*- coding: utf-8 -*-
import scrapy

class FinepSpider(scrapy.Spider):
    """
    Este é o seu crawler, salvo em um arquivo Python separado.
    O run_update.py irá executá-lo.
    """
    name = 'finep_editais'
    
    allowed_domains = ['finep.gov.br']
    # --- MODIFICADO PARA DEMONSTRAÇÃO ---
    # Busca editais 'encerrada' em vez de 'aberta'
    start_urls = ['http://www.finep.gov.br/chamadas-publicas?situacao=encerrada']

    def parse(self, response):
        links_dos_editais = response.css('div.item h3 a::attr(href)').getall()
        for link in links_dos_editais:
            yield response.follow(link, callback=self.parse_item_details)

        # --- MODIFICADO PARA DEMONSTRAÇÃO ---
        # Paginação foi comentada para limitar a 1 página (aprox. 10 editais)
        # link_proxima_pagina = response.css('li.pagination-next a::attr(href)').get()
        # if link_proxima_pagina is not None:
        #     yield response.follow(link_proxima_pagina, callback=self.parse)

    def parse_item_details(self, response):
        titulo = response.css('h2.tit_pag a::text').get()
        data_publicacao = response.xpath('//div[@class="tit" and contains(text(), "Data de Publicação")]/following-sibling::div[@class="text"]/text()').get()
        prazo_final = response.xpath('//div[@class="tit" and contains(text(), "Prazo para envio de propostas até:")]/following-sibling::div[@class="text"]/text()').get()
        publico_alvo_lista = response.xpath('//div[@class="tit" and contains(text(), "Público-alvo")]/following-sibling::div[@class="text"]/descendant-or-self::*/text()').getall()
        publico_alvo = " ".join([texto.strip() for texto in publico_alvo_lista]).strip()
        
        areas_interesse_lista = response.xpath('//div[@class="tit" and contains(text(), "Tema(s)")]/following-sibling::div[@class="text"]/descendant-or-self::*/text()').getall()
        if not areas_interesse_lista:
            areas_interesse_lista = response.css('div.tema span::text').getall()
        
        tema = [texto.strip() for texto in areas_interesse_lista if texto.strip()]

        link_pdf_relativo = response.css('td.destaque_documentos a[href$=".pdf"]::attr(href)').get()
        link_pdf_completo = response.urljoin(link_pdf_relativo) if link_pdf_relativo else None

        yield {
            'Título': titulo.strip() if titulo else 'Título não encontrado',
            'Data de Publicação': data_publicacao.strip() if data_publicacao else 'Não encontrada',
            'Prazo Final': prazo_final.strip() if prazo_final else 'Prazo não encontrado',
            'Público-alvo': publico_alvo if publico_alvo else 'Não especificado',
            'Tema': tema if tema else 'Não especificado',
            'url': response.url,
            'Link PDF': link_pdf_completo if link_pdf_completo else 'Link não encontrado'
        }

