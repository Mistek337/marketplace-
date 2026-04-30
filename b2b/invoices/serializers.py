from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from catalog.models import SKU

from .models import Invoice, InvoiceLine


class InvoiceLineInputSerializer(serializers.Serializer):
    skuId = serializers.PrimaryKeyRelatedField(queryset=SKU.objects.all(), source='sku')
    quantity = serializers.IntegerField(min_value=1)


class InvoiceLineOutputSerializer(serializers.ModelSerializer):
    skuId = serializers.IntegerField(source='sku_id', read_only=True)

    class Meta:
        model = InvoiceLine
        fields = ('skuId', 'quantity')


class InvoiceDetailSerializer(serializers.ModelSerializer):
    lines = InvoiceLineOutputSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = ('id', 'status', 'note', 'created_at', 'lines')


class InvoiceCreateSerializer(serializers.Serializer):
    """
    POST /api/v1/invoices — создать накладную (ещё не принята на склад).
    """

    lines = InvoiceLineInputSerializer(many=True, min_length=1)
    note = serializers.CharField(required=False, allow_blank=True, max_length=1024, default='')

    def create(self, validated_data: dict) -> Invoice:
        lines_data = validated_data['lines']
        note = validated_data.get('note', '')
        with transaction.atomic():
            invoice = Invoice.objects.create(note=note)
            for row in lines_data:
                InvoiceLine.objects.create(
                    invoice=invoice,
                    sku=row['sku'],
                    quantity=row['quantity'],
                )
        return invoice

    def to_representation(self, instance: Invoice) -> dict:
        return InvoiceDetailSerializer(instance, context=self.context).data


class InvoiceAcceptSerializer(serializers.Serializer):
    """
    POST /api/v1/invoices/accept — принять накладную: статус ACCEPTED, приход по остаткам SKU.
    """

    invoiceId = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.filter(status=Invoice.Status.CREATED),
        source='invoice',
    )

    def create(self, validated_data: dict) -> Invoice:
        invoice: Invoice = validated_data['invoice']
        with transaction.atomic():
            invoice_locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
            if invoice_locked.status != Invoice.Status.CREATED:
                raise serializers.ValidationError(
                    {'invoiceId': 'Накладная уже принята или отменена.'},
                )
            lines = list(
                InvoiceLine.objects.select_related('sku').filter(invoice=invoice_locked),
            )
            if not lines:
                raise serializers.ValidationError({'invoiceId': 'В накладной нет позиций.'})
            for line in lines:
                SKU.objects.filter(pk=line.sku_id).update(
                    active_quantity=F('active_quantity') + line.quantity,
                )
            invoice_locked.status = Invoice.Status.ACCEPTED
            invoice_locked.save(update_fields=['status'])
        return invoice_locked

    def to_representation(self, instance: Invoice) -> dict:
        return InvoiceDetailSerializer(instance, context=self.context).data
