"""Logique métier des cotisations (§ 5.5.5, § 5.7.2)."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.core.services import journaliser
from apps.membres.models import Membre
from apps.notifications.services import creer_notification

from .models import Cotisation, Paiement


def calculer_statut(cotisation, aujourdhui=None):
    """Détermine le statut d'une cotisation (RG04, RG06).

    Fonction pure : elle ne dépend que de l'état de la cotisation et de la date.
    """
    aujourdhui = aujourdhui or date.today()
    if cotisation.montant_paye >= cotisation.montant_du:
        return Cotisation.Statut.PAYEE
    if cotisation.date_echeance < aujourdhui:
        return Cotisation.Statut.EN_RETARD
    if cotisation.montant_paye > 0:
        return Cotisation.Statut.PARTIEL
    return Cotisation.Statut.EN_ATTENTE


@transaction.atomic
def emettre_cotisations_exercice(exercice, montant, date_echeance, utilisateur=None):
    """Émet les appels de cotisation d'un exercice (RG04)."""
    membres = Membre.objects.actifs()
    creees, ignorees = [], 0
    for membre in membres:
        cotisation, cree = Cotisation.objects.get_or_create(
            membre=membre, exercice=exercice,
            defaults={'montant_du': montant,
                      'date_echeance': date_echeance,
                      'statut': Cotisation.Statut.EN_ATTENTE})
        if cree:
            creees.append(cotisation)
        else:
            ignorees += 1          # contrainte d'unicité respectée
    journaliser(utilisateur, 'EMISSION_COTISATIONS',
                f'exercice {exercice} : {len(creees)} créées, {ignorees} ignorées')
    return creees, ignorees


@transaction.atomic
def enregistrer_paiement(cotisation, montant, mode, reference='', utilisateur=None):
    """Enregistre un paiement rattaché à une cotisation existante (RG05)."""
    montant = Decimal(montant)
    if montant <= 0:
        raise ValidationError("Le montant doit être strictement positif.")

    # Reverrouille la ligne au tout début de la transaction plutôt que de
    # se fier à l'objet passé par l'appelant, potentiellement chargé avant
    # que la transaction ne commence : sans ce verrou, deux saisies
    # simultanées sur la même cotisation peuvent lire le même reste à
    # payer, passer toutes deux la validation, puis s'écraser l'une
    # l'autre à l'enregistrement — le paiement resterait tracé dans
    # Paiement, mais montant_paye/statut de la cotisation perdrait l'une
    # des deux mises à jour.
    cotisation = Cotisation.objects.select_for_update().get(pk=cotisation.pk)

    reste = cotisation.montant_du - cotisation.montant_paye
    if montant > reste:
        raise ValidationError(
            f"Montant supérieur au reste à payer ({reste} FCFA).")

    paiement = Paiement.objects.create(
        cotisation=cotisation, montant=montant, mode=mode,
        reference=reference, enregistre_par=utilisateur,
        date_paiement=timezone.now())

    cotisation.montant_paye += montant
    cotisation.statut = calculer_statut(cotisation)
    cotisation.save(update_fields=['montant_paye', 'statut'])

    journaliser(utilisateur, 'ENREGISTREMENT_PAIEMENT',
                f'cotisation {cotisation.pk} : +{montant} FCFA')
    notifier_recu_paiement(paiement, cotisation)
    return paiement


def notifier_recu_paiement(paiement, cotisation):
    """Envoie au membre un reçu du versement qu'il vient d'effectuer (RG05),
    avec le même reçu joint en PDF (voir `generer_recu_pdf`)."""
    creer_notification(
        destinataire=cotisation.membre.email,
        type_notification='RECU_PAIEMENT',
        objet=f"Reçu de cotisation {cotisation.exercice} — AFEMC-CI",
        gabarit='notifications/recu_paiement.txt',
        contexte={
            'membre': cotisation.membre.nom_complet(),
            'matricule': cotisation.membre.matricule,
            'exercice': cotisation.exercice,
            'montant_verse': str(paiement.montant),
            'mode': paiement.get_mode_display(),
            'reference': paiement.reference or '—',
            'date_paiement': paiement.date_paiement.strftime('%d/%m/%Y'),
            'montant_du': str(cotisation.montant_du),
            'montant_paye_cumule': str(cotisation.montant_paye),
            'reste': str(cotisation.reste_a_payer),
            'statut': cotisation.get_statut_display(),
        },
        membre=cotisation.membre,
        piece_jointe_generateur='apps.cotisations.services.generer_recu_pdf')


_CARACTERES_HORS_LATIN1 = {
    '—': '-', '–': '-',              # tirets cadratin/demi-cadratin
    '‘': "'", '’': "'",              # apostrophes courbes
    '“': '"', '”': '"',              # guillemets courbes
    '…': '...',                           # points de suspension
}


def _texte_pdf(valeur):
    """Les polices de base de fpdf2 (Helvetica) ne supportent que Latin-1 :
    un tiret cadratin ou une apostrophe courbe suffit à faire échouer toute
    la génération (`FPDFUnicodeEncodingException`). Remplace les caractères
    typographiques usuels par leur équivalent ASCII plutôt que de risquer
    qu'un texte imprévu (référence de paiement, nom d'un membre…) casse le
    reçu — les accents français, eux, sont bien dans Latin-1 et inchangés.
    """
    texte = str(valeur)
    for cherche, remplace in _CARACTERES_HORS_LATIN1.items():
        texte = texte.replace(cherche, remplace)
    return texte


def generer_recu_pdf(contexte):
    """Reçu de cotisation en PDF, à partir du même `contexte` que le courriel.

    Résolue dynamiquement par `apps.notifications.services` (via le chemin
    stocké dans `piece_jointe_generateur`), jamais importée ni stockée :
    régénérée à chaque tentative d'envoi, comme le corps du courriel.
    """
    from fpdf import FPDF, XPos, YPos

    pdf = FPDF(format='A4')
    pdf.set_margin(20)
    pdf.add_page()

    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(18, 32, 79)                       # afemc-marine
    pdf.cell(0, 10, 'AFEMC-CI', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 6, _texte_pdf("Association des Femmes Enseignantes Chercheures de Côte d'Ivoire"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    pdf.set_draw_color(224, 18, 126)                     # afemc-rose
    pdf.set_line_width(0.8)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(8)

    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(18, 32, 79)
    pdf.cell(0, 8, _texte_pdf(f"Reçu de cotisation — Exercice {contexte['exercice']}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    lignes = [
        ('Membre', contexte['membre']),
        ("N° d'adhérente", contexte['matricule']),
        ('Montant versé', f"{contexte['montant_verse']} FCFA"),
        ('Mode de règlement', contexte['mode']),
        ('Référence', contexte['reference']),
        ('Date du versement', contexte['date_paiement']),
        ('Montant total appelé', f"{contexte['montant_du']} FCFA"),
        ('Total réglé à ce jour', f"{contexte['montant_paye_cumule']} FCFA"),
        ('Reste à régler', f"{contexte['reste']} FCFA"),
        ('Statut de la cotisation', contexte['statut']),
    ]
    for libelle, valeur in lignes:
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(60, 8, _texte_pdf(libelle))
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, _texte_pdf(valeur), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 5, _texte_pdf("Ce document tient lieu de reçu. Conservez-le pour vos archives."))

    nom_fichier = f"recu_cotisation_{contexte['exercice']}.pdf"
    return nom_fichier, bytes(pdf.output()), 'application/pdf'


def indicateurs_exercice(exercice, section=None):
    """Agrégats financiers de l'exercice, en une seule requête (§ 5.7.2)."""
    cotisations = Cotisation.objects.filter(exercice=exercice)
    if section:
        cotisations = cotisations.filter(membre__section=section)

    agr = cotisations.aggregate(
        total_du=Sum('montant_du'),
        total_paye=Sum('montant_paye'),
        nb_total=Count('id'),
        nb_payees=Count('id', filter=Q(statut=Cotisation.Statut.PAYEE)),
        nb_retard=Count('id', filter=Q(statut=Cotisation.Statut.EN_RETARD)),
        nb_partiel=Count('id', filter=Q(statut=Cotisation.Statut.PARTIEL)),
    )
    total_du = agr['total_du'] or Decimal('0')
    total_paye = agr['total_paye'] or Decimal('0')

    return {
        **agr,
        'total_du': total_du,
        'total_paye': total_paye,
        'reste_a_recouvrer': total_du - total_paye,
        'taux_recouvrement': (total_paye / total_du * 100) if total_du else Decimal('0'),
    }
