//
//  Item.swift
//  ByteBite-AI
//
//  Created by Andrea Filiberto Lucas on 14/11/2024.
//

import Foundation
import SwiftData

@Model
final class Item {
    var timestamp: Date
    
    init(timestamp: Date) {
        self.timestamp = timestamp
    }
}
