// Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
// Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
// Shark Support settings - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

import UM 1.5 as UM
import Cura 1.0 as Cura

UM.Dialog
{
    id: dialog
    title: "Shark Support " + manager.version + " (Built " + manager.buildDate + ") - WIP"
    width: 780 * screenScaleFactor
    height: 660 * screenScaleFactor
    minimumWidth: 460 * screenScaleFactor
    minimumHeight: 420 * screenScaleFactor
    backgroundColor: UM.Theme.getColor("main_background")

    property int refresh: 0

    ColumnLayout
    {
        anchors.fill: parent
        spacing: UM.Theme.getSize("default_margin").height

        Connections
        {
            target: manager
            function onSettingsChanged() { dialog.refresh += 1 }
        }

        UM.Label
        {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "Select a model that is already tilted the way you will print it. Pick a face to support it, or " +
                  "press Auto for every big flat face in the angle range below. The same buttons are in the " +
                  "shark-fin tool in the left toolbar."
        }

        ScrollView
        {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.vertical: UM.ScrollBar { }

            ColumnLayout
            {
                width: scroll.availableWidth
                spacing: Math.round(UM.Theme.getSize("narrow_margin").height / 2)

                GridLayout
                {
                    columns: 2
                    columnSpacing: UM.Theme.getSize("default_margin").width * 2
                    rowSpacing: Math.round(UM.Theme.getSize("narrow_margin").height / 2)
                    Layout.fillWidth: true

                    Repeater
                    {
                        model: manager.fields
                        delegate: RowLayout
                        {
                            Layout.fillWidth: true
                            UM.Label
                            {
                                text: modelData.label
                                Layout.preferredWidth: 150 * screenScaleFactor
                                UM.ToolTip
                                {
                                    tooltipText: modelData.tip
                                    visible: labelHover.containsMouse
                                }
                                MouseArea { id: labelHover; anchors.fill: parent; hoverEnabled: true }
                            }
                            UM.TextFieldWithUnit
                            {
                                Layout.preferredWidth: 130 * screenScaleFactor
                                Layout.preferredHeight: UM.Theme.getSize("setting_control").height
                                unit: modelData.unit
                                text: { dialog.refresh; return manager.getValue(modelData.key) }
                                validator: RegularExpressionValidator { regularExpression: /^[0-9]*[.]?[0-9]*$/ }
                                onEditingFinished: manager.setValue(modelData.key, text)
                            }
                            Item { Layout.fillWidth: true }
                        }
                    }
                }

                Repeater
                {
                    model: manager.switches
                    delegate: UM.CheckBox
                    {
                        Layout.fillWidth: true
                        text: modelData.label
                        checked: { dialog.refresh; return manager.getValue(modelData.key) === "true" }
                        onClicked: manager.setValue(modelData.key, checked ? "true" : "false")
                    }
                }
            }
        }

        UM.Label
        {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: manager.status
            color: UM.Theme.getColor("text_medium")
        }

        UM.Label
        {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            font: UM.Theme.getFont("small")
            color: UM.Theme.getColor("text_medium")
            text: "v" + manager.version + " - built " + manager.buildDate +
                  " - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN - Copyright Matthew Armstrong, PolyForm Noncommercial 1.0.0, no warranty"
        }
    }

    leftButtons:
    [
        Cura.SecondaryButton
        {
            text: "Defaults"
            onClicked: manager.resetDefaults()
        },
        Cura.SecondaryButton
        {
            text: "Remove all fins"
            onClicked: manager.removeFins()
        }
    ]

    rightButtons:
    [
        Cura.SecondaryButton
        {
            text: "Close"
            onClicked: dialog.close()
        },
        Cura.SecondaryButton
        {
            text: "Pick a face"
            onClicked: { manager.startPicking(); dialog.close() }
        },
        Cura.PrimaryButton
        {
            text: "Auto: all faces"
            onClicked: manager.addFins()
        }
    ]
}
