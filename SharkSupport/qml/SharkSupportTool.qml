// Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
// Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
// Shark Support toolbar panel - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN

import QtQuick 2.15
import QtQuick.Layouts 1.15

import UM 1.5 as UM
import Cura 1.0 as Cura

Item
{
    id: base
    width: column.implicitWidth
    height: column.implicitHeight

    property bool picking: UM.Controller.properties.getValue("PickMode") === true

    ColumnLayout
    {
        id: column
        spacing: UM.Theme.getSize("default_margin").height

        UM.Label
        {
            text: "Shark Support"
            font: UM.Theme.getFont("default_bold")
        }

        RowLayout
        {
            spacing: UM.Theme.getSize("default_margin").width

            Cura.PrimaryButton
            {
                id: pickButton
                text: base.picking ? "Picking... (click a face)" : "Pick face"
                tooltip: "Then click the underside face of the selected model that needs supporting."
                onClicked: UM.Controller.setProperty("PickMode", !base.picking)
            }
            Cura.SecondaryButton
            {
                text: "Auto"
                tooltip: "Fins under every big tilted flat face of the selected model(s)."
                onClicked: UM.Controller.triggerAction("autoFins")
            }
        }

        RowLayout
        {
            spacing: UM.Theme.getSize("default_margin").width

            Cura.SecondaryButton
            {
                text: "Remove all"
                tooltip: "Remove every Shark fin object from the build plate."
                onClicked: UM.Controller.triggerAction("removeFins")
            }
            Cura.SecondaryButton
            {
                text: "Settings..."
                onClicked: UM.Controller.triggerAction("openSettings")
            }
        }

        UM.Label
        {
            Layout.preferredWidth: 300 * screenScaleFactor
            wrapMode: Text.WordWrap
            color: UM.Theme.getColor("text_medium")
            text: UM.Controller.properties.getValue("Status") || ""
        }

        UM.Label
        {
            Layout.preferredWidth: 300 * screenScaleFactor
            wrapMode: Text.WordWrap
            font: UM.Theme.getFont("small")
            color: UM.Theme.getColor("text_medium")
            text: "v" + (UM.Controller.properties.getValue("Version") || "") + " - work in progress"
        }
    }
}
